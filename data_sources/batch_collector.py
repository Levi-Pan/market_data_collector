#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/27 14:35
# software:Vscode
# brief : 小批量采集美股日线并保存运行状态

import csv
import json
import logging
import os
import tempfile
import time
import urllib.error
from datetime import datetime, timezone

from data_sources.stock_universe import save_stock_universe
from data_sources.symbol_cache import resolve_cached_symbol
from data_sources.tencent_daily import fetch_daily_prices, save_daily_prices
from data_sources.trading_calendar import get_completed_trading_dates
from standard_module.config import (
    BATCH_MAX_ATTEMPTS,
    BATCH_RETRY_SECONDS,
    BATCH_SLEEP_SECONDS,
    BATCH_STATE_PATH,
    BATCH_SYMBOL_LIMIT,
    DAILY_OUTPUT_DIR,
    REQUEST_BAR_COUNT,
    SAVE_BAR_COUNT,
    UNIVERSE_OUTPUT_PATH,
)


def read_batch_symbols():
    """
    从官方名单读取本次小批量证券代码。

    :return: 不重复的标准代码列表
    """
    symbols = []
    seen = set()
    with open(UNIVERSE_OUTPUT_PATH, encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if "symbol" not in (reader.fieldnames or []):
            raise ValueError("证券名单缺少symbol字段")
        for row in reader:
            symbol = (row.get("symbol") or "").strip().upper()
            if not symbol or symbol in seen:
                raise ValueError(f"证券名单存在空代码或重复代码：{symbol}")
            seen.add(symbol)
            symbols.append(symbol)
            if BATCH_SYMBOL_LIMIT > 0 and len(symbols) >= BATCH_SYMBOL_LIMIT:
                break

    if not symbols:
        raise ValueError("证券名单为空")
    return symbols


def write_batch_state(state):
    """
    原子替换批次状态文件，避免读取到半份JSON。

    :param state: 本轮采集状态字典
    :return: 无
    """
    output_dir = os.path.dirname(BATCH_STATE_PATH)
    os.makedirs(output_dir, exist_ok=True)
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8",
            dir=output_dir,
            suffix=".tmp",
            delete=False,
        ) as stream:
            temporary_path = stream.name
            json.dump(state, stream, ensure_ascii=False, indent=2)
        os.replace(temporary_path, BATCH_STATE_PATH)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)


def collect_one_symbol(symbol, expected_dates):
    """
    获取并保存单只证券，仅对网络错误进行有限重试。

    :param symbol: 标准证券代码
    :param expected_dates: 整批共用的已收盘交易日期
    :return: 腾讯代码及输出文件路径
    """
    for attempt in range(1, BATCH_MAX_ATTEMPTS + 1):
        try:
            provider_symbol = resolve_cached_symbol(symbol)
            prices = fetch_daily_prices(provider_symbol, REQUEST_BAR_COUNT)
            output_path = save_daily_prices(
                prices,
                provider_symbol,
                DAILY_OUTPUT_DIR,
                SAVE_BAR_COUNT,
                expected_dates,
            )
            return provider_symbol, output_path
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt >= BATCH_MAX_ATTEMPTS:
                raise
            logging.warning(
                "%s网络请求失败，等待重试：%s/%s",
                symbol, attempt, BATCH_MAX_ATTEMPTS,
            )
            time.sleep(BATCH_RETRY_SECONDS)

    raise RuntimeError(f"采集未完成：{symbol}")


def run_batch_collection():
    """
    更新名单并执行有数量上限的批量采集。

    :return: 全部成功返回0，存在失败返回2
    """
    if BATCH_SYMBOL_LIMIT < 0:
        raise ValueError("采集数量不能为负数")
    if BATCH_MAX_ATTEMPTS <= 0:
        raise ValueError("尝试次数必须大于0")
    if BATCH_SLEEP_SECONDS < 0 or BATCH_RETRY_SECONDS < 0:
        raise ValueError("等待时间不能为负数")

    expected_dates = get_completed_trading_dates(SAVE_BAR_COUNT)
    save_stock_universe()
    symbols = read_batch_symbols()
    state = {
        "status": "RUNNING",
        "started_at": datetime.now(timezone.utc).isoformat(),
        "finished_at": None,
        "target_date": expected_dates[-1],
        "scope_limit": BATCH_SYMBOL_LIMIT,
        "total": len(symbols),
        "success": 0,
        "failed": 0,
        "results": [],
    }
    write_batch_state(state)
    logging.info(
        "开始采集%s只证券，目标交易日：%s",
        len(symbols), expected_dates[-1],
    )

    try:
        for index, symbol in enumerate(symbols, start=1):
            result = {
                "symbol": symbol,
                "provider_symbol": "",
                "status": "FAILED",
                "path": "",
                "error": "",
            }
            try:
                provider_symbol, output_path = collect_one_symbol(
                    symbol, expected_dates,
                )
                result.update({
                    "provider_symbol": provider_symbol,
                    "status": "SUCCESS",
                    "path": output_path,
                })
                state["success"] += 1
                logging.info("[%s/%s] %s成功", index, len(symbols), symbol)
            except Exception as error:
                result["error"] = f"{type(error).__name__}: {error}"
                state["failed"] += 1
                logging.error(
                    "[%s/%s] %s失败：%s",
                    index, len(symbols), symbol, error,
                )
            state["results"].append(result)
            if index % 20 == 0:
                write_batch_state(state)
            if index < len(symbols):
                time.sleep(BATCH_SLEEP_SECONDS)
    finally:
        state["finished_at"] = datetime.now(timezone.utc).isoformat()
        if len(state["results"]) < len(symbols):
            state["status"] = "INTERRUPTED"
        else:
            state["status"] = "COMPLETED" if state["failed"] == 0 else "PARTIAL"
        write_batch_state(state)

    logging.info(
        "采集结束：成功%s，失败%s，状态文件：%s",
        state["success"], state["failed"], BATCH_STATE_PATH,
    )
    return 0 if state["failed"] == 0 else 2