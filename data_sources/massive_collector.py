#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/29 13:10
# software:Vscode
# brief : 下载美股30个交易日日线并原子发布数据批次

import csv
import json
import logging
import math
import os
import re
import shutil
import tempfile
import time
import urllib.error
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from data_sources.massive_daily import fetch_market_daily
from data_sources.trading_calendar import get_completed_trading_dates
from standard_module.config import (
    MASSIVE_MAX_ATTEMPTS,
    MASSIVE_OUTPUT_DIR,
    MASSIVE_REQUEST_INTERVAL_SECONDS,
    SAVE_BAR_COUNT,
    MASSIVE_KEEP_BATCHES,
)


def fetch_with_retry(trading_date):
    """
    限速请求单日行情，仅重试网络错误和可恢复HTTP错误。

    :param trading_date: 交易日期
    :return: 原始日线列表
    """
    for attempt in range(1, MASSIVE_MAX_ATTEMPTS + 1):
        time.sleep(MASSIVE_REQUEST_INTERVAL_SECONDS)
        try:
            return fetch_market_daily(trading_date)
        except Exception as error:
            cause = error.__cause__ or error
            if isinstance(cause, urllib.error.HTTPError):
                retryable = cause.code == 429 or 500 <= cause.code < 600
            else:
                retryable = isinstance(
                    cause,
                    (urllib.error.URLError, TimeoutError, ConnectionError),
                )
            if not retryable or attempt >= MASSIVE_MAX_ATTEMPTS:
                raise
            logging.warning(
                "%s请求失败，准备重试：%s/%s",
                trading_date, attempt, MASSIVE_MAX_ATTEMPTS,
            )

    raise RuntimeError(f"下载未完成：{trading_date}")


def normalize_daily(row, trading_date):
    """
    校验并转换一条Massive日线。

    :param row: Massive原始日线
    :param trading_date: 本次请求的交易日期
    :return: 标准日线字典
    """
    symbol = row["T"]
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._$^-]*", symbol):
        raise ValueError(f"证券代码不能作为文件名：{symbol}")

    record_date = datetime.fromtimestamp(
        row["t"] / 1000,
        tz=timezone.utc,
    ).astimezone(ZoneInfo("America/New_York")).date().isoformat()
    if record_date != trading_date:
        raise ValueError(f"行情日期不一致：{symbol}，{record_date}")

    prices = {
        field: float(row[source])
        for field, source in (
            ("open", "o"), ("high", "h"),
            ("low", "l"), ("close", "c"), ("volume", "v"),
        )
    }
    if not all(math.isfinite(value) for value in prices.values()):
        raise ValueError(f"行情存在非有限数值：{symbol}")
    if min(prices[field] for field in ("open", "high", "low", "close")) <= 0:
        raise ValueError(f"价格必须大于0：{symbol}")
    if prices["volume"] < 0:
        raise ValueError(f"成交量不能为负数：{symbol}")
    if prices["high"] < max(prices["open"], prices["close"], prices["low"]):
        raise ValueError(f"最高价异常：{symbol}")
    if prices["low"] > min(prices["open"], prices["close"], prices["high"]):
        raise ValueError(f"最低价异常：{symbol}")

    return {"symbol": symbol, "date": trading_date, **prices}


def get_completed_batch(dates):
    """
    检查当前已发布批次是否覆盖目标日期窗口。

    :param dates: 本次需要的交易日期列表
    :return: 有效批次路径，不满足时返回None
    """
    try:
        with open(
            os.path.join(MASSIVE_OUTPUT_DIR, "current.json"),
            encoding="utf-8",
        ) as stream:
            pointer = json.load(stream)
        batch_name = pointer["batch"]
        if not re.fullmatch(r"batch-\d{8}T\d{12}Z", batch_name):
            return None

        batch_dir = os.path.join(MASSIVE_OUTPUT_DIR, batch_name)
        with open(
            os.path.join(batch_dir, "summary.json"),
            encoding="utf-8",
        ) as stream:
            summary = json.load(stream)
        if (
            summary.get("status") != "COMPLETED"
            or summary.get("source") != "massive"
            or summary.get("dates") != dates
            or summary.get("success", 0) <= 0
        ):
            return None

        price_dir = os.path.join(batch_dir, "prices")
        count = sum(
            entry.is_file() and entry.name.endswith(".csv")
            for entry in os.scandir(price_dir)
        )
        return batch_dir if count == summary["success"] else None
    except (OSError, ValueError, KeyError, TypeError):
        return None


def cleanup_old_batches(current_batch):
    """
    保留当前批次及最近的历史成功批次，清理更旧的数据。

    :param current_batch: 当前成功批次路径
    :return: 无
    """
    output_root = os.path.realpath(MASSIVE_OUTPUT_DIR)
    candidates = []
    for entry in os.scandir(output_root):
        if (
            entry.is_symlink()
            or not entry.is_dir()
            or not re.fullmatch(r"batch-\d{8}T\d{12}Z", entry.name)
        ):
            continue
        batch_path = os.path.realpath(entry.path)
        if os.path.dirname(batch_path) != output_root:
            continue
        try:
            with open(
                os.path.join(batch_path, "summary.json"),
                encoding="utf-8",
            ) as stream:
                summary = json.load(stream)
            if (
                summary.get("source") == "massive"
                and summary.get("status") == "COMPLETED"
            ):
                candidates.append(batch_path)
        except (OSError, ValueError, AttributeError):
            continue

    current_batch = os.path.realpath(current_batch)
    history = sorted(
        (path for path in candidates if path != current_batch),
        reverse=True,
    )
    for batch_path in history[MASSIVE_KEEP_BATCHES - 1:]:
        try:
            shutil.rmtree(batch_path)
            logging.info("已清理旧批次：%s", batch_path)
        except OSError:
            logging.warning(
                "旧批次清理失败：%s", batch_path, exc_info=True,
            )


def run_market_collection():
    """
    下载完整日期窗口，生成CSV后发布当前批次指针。

    :return: 成功批次的完整路径
    """
    if MASSIVE_REQUEST_INTERVAL_SECONDS < 13 or MASSIVE_MAX_ATTEMPTS < 1:
        raise ValueError("请求间隔至少13秒，尝试次数至少1次")

    if MASSIVE_KEEP_BATCHES < 2:
        raise ValueError("至少保留两个成功批次")

    dates = get_completed_trading_dates(SAVE_BAR_COUNT)
    os.makedirs(MASSIVE_OUTPUT_DIR, exist_ok=True)
    completed_batch = get_completed_batch(dates)
    if completed_batch:
        logging.info("目标交易日%s已采集成功，跳过下载", dates[-1])
        cleanup_old_batches(completed_batch)
        return completed_batch
    staging_dir = tempfile.mkdtemp(
        prefix=".building-", dir=MASSIVE_OUTPUT_DIR,
    )
    pointer_path = None
    try:
        stocks = {}
        for index, trading_date in enumerate(dates, start=1):
            rows = fetch_with_retry(trading_date)
            seen = set()
            for row in rows:
                price = normalize_daily(row, trading_date)
                symbol = price["symbol"]
                if symbol in seen:
                    raise ValueError(f"同日证券重复：{trading_date}，{symbol}")
                seen.add(symbol)
                stocks.setdefault(symbol, []).append(price)
            logging.info(
                "[%s/%s] %s获取成功：%s只",
                index, len(dates), trading_date, len(rows),
            )

        price_dir = os.path.join(staging_dir, "prices")
        os.makedirs(price_dir)
        skipped = []
        success = 0
        for symbol, prices in sorted(stocks.items()):
            if [price["date"] for price in prices] != dates:
                skipped.append({
                    "symbol": symbol,
                    "reason": "窗口内交易日不完整",
                    "actual_count": len(prices),
                })
                continue
            with open(
                os.path.join(price_dir, f"{symbol}.csv"),
                "w", encoding="utf-8-sig", newline="",
            ) as stream:
                writer = csv.DictWriter(
                    stream,
                    fieldnames=[
                        "symbol", "date", "open", "high",
                        "low", "close", "volume",
                    ],
                )
                writer.writeheader()
                writer.writerows(prices)
            success += 1

        if success == 0:
            raise ValueError("没有证券通过完整日期窗口校验，停止发布")

        summary = {
            "status": "COMPLETED",
            "source": "massive",
            "adjustment": "split_adjusted",
            "dates": dates,
            "success": success,
            "skipped": skipped,
            "finished_at": datetime.now(timezone.utc).isoformat(),
        }
        with open(
            os.path.join(staging_dir, "summary.json"),
            "w", encoding="utf-8",
        ) as stream:
            json.dump(summary, stream, ensure_ascii=False, indent=2)

        batch_name = "batch-" + datetime.now(timezone.utc).strftime(
            "%Y%m%dT%H%M%S%fZ"
        )
        batch_dir = os.path.join(MASSIVE_OUTPUT_DIR, batch_name)
        os.rename(staging_dir, batch_dir)

        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8",
            dir=MASSIVE_OUTPUT_DIR, suffix=".tmp", delete=False,
        ) as stream:
            pointer_path = stream.name
            json.dump(
                {"batch": batch_name, "target_date": dates[-1]},
                stream, ensure_ascii=False, indent=2,
            )
        os.replace(
            pointer_path,
            os.path.join(MASSIVE_OUTPUT_DIR, "current.json"),
        )
        logging.info(
            "发布成功：%s只，日期不完整跳过%s只，目录：%s",
            success, len(skipped), batch_dir,
        )
        cleanup_old_batches(batch_dir)
        return batch_dir
    finally:
        if os.path.isdir(staging_dir):
            shutil.rmtree(staging_dir)
        if pointer_path and os.path.exists(pointer_path):
            os.remove(pointer_path)