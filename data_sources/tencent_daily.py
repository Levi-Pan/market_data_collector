#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/27 13:31
# software:Vscode
# brief : 获取腾讯财经单只股票历史日线

import json
import urllib.parse
import urllib.request
import csv
import os
import tempfile
import re
import math
from datetime import date

from standard_module.config import (
    REQUEST_TIMEOUT_SECONDS,
    TENCENT_KLINE_URL,
    TENCENT_SYMBOL_SEARCH_URL,
)


def fetch_daily_prices(provider_symbol, count):
    """
    获取单只股票的历史日线并统一字段。

    :param provider_symbol: 腾讯股票代码，例如usAAPL.OQ或usIBM.N
    :param count: 请求的日线数量
    :return: 按日期升序排列的行情字典列表，尚未校验复权和交易日完整性
    """
    if not provider_symbol or count <= 0:
        raise ValueError("股票代码不能为空，请求数量必须大于0")

    query = urllib.parse.urlencode({
        "param": f"{provider_symbol},day,,,{count},qfq",
    })
    request = urllib.request.Request(
        f"{TENCENT_KLINE_URL}?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(
        request, timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        payload = json.loads(response.read().decode("utf-8-sig"))

    if payload.get("code") != 0:
        raise RuntimeError(f"行情接口返回失败：{payload.get('msg', '')}")

    stock_data = (payload.get("data") or {}).get(provider_symbol) or {}
    raw_rows = stock_data.get("qfqday") or stock_data.get("day") or []
    if not raw_rows:
        raise RuntimeError(f"未获取到日线：{provider_symbol}")

    prices = []
    for row in raw_rows:
        if not isinstance(row, list) or len(row) < 6:
            raise ValueError(f"日线字段不完整：{provider_symbol}")
        prices.append({
            "symbol": provider_symbol,
            "date": row[0],
            "open": float(row[1]),
            "high": float(row[3]),
            "low": float(row[4]),
            "close": float(row[2]),
            "volume": float(row[5]),
        })

    return sorted(prices, key=lambda item: item["date"])


def validate_daily_prices(prices, provider_symbol):
    """
    校验日线字段、重复日期和价格关系，并按日期排序。

    :param prices: 待校验的行情列表
    :param provider_symbol: 当前股票的腾讯代码
    :return: 校验通过并按日期升序排列的行情列表
    """
    validated = []
    seen_dates = set()

    for price in prices:
        try:
            trading_date = date.fromisoformat(price["date"]).isoformat()
            values = {
                field: float(price[field])
                for field in ("open", "high", "low", "close", "volume")
            }
        except (KeyError, TypeError, ValueError, OverflowError) as error:
            raise ValueError(f"日线字段格式错误：{provider_symbol}") from error

        if price.get("symbol") != provider_symbol:
            raise ValueError(f"日线股票代码不一致：{provider_symbol}")
        if trading_date in seen_dates:
            raise ValueError(f"日线日期重复：{provider_symbol}，{trading_date}")
        if not all(math.isfinite(value) for value in values.values()):
            raise ValueError(f"日线包含NaN或无穷值：{provider_symbol}，{trading_date}")

        price_values = [values[field] for field in ("open", "high", "low", "close")]
        if min(price_values) <= 0:
            raise ValueError(f"价格必须大于0：{provider_symbol}，{trading_date}")
        if values["high"] < max(price_values):
            raise ValueError(f"最高价字段异常：{provider_symbol}，{trading_date}")
        if values["low"] > min(price_values):
            raise ValueError(f"最低价字段异常：{provider_symbol}，{trading_date}")
        if values["volume"] < 0:
            raise ValueError(f"成交量不能为负：{provider_symbol}，{trading_date}")

        seen_dates.add(trading_date)
        validated.append({
            "symbol": provider_symbol,
            "date": trading_date,
            **values,
        })

    return sorted(validated, key=lambda item: item["date"])


def select_trading_window(prices, provider_symbol, expected_dates):
    """
    校验行情并选取指定交易日，排除窗口外及未收盘数据。

    :param prices: 接口返回的行情列表
    :param provider_symbol: 腾讯股票代码
    :param expected_dates: 按升序排列的已收盘交易日期列表
    :return: 与预期交易日完全对应的行情列表
    """
    if not expected_dates or expected_dates != sorted(set(expected_dates)):
        raise ValueError("预期交易日期必须非空、升序且不重复")

    validated = validate_daily_prices(prices, provider_symbol)
    by_date = {price["date"]: price for price in validated}
    missing_dates = [
        trading_date
        for trading_date in expected_dates
        if trading_date not in by_date
    ]
    if missing_dates:
        raise ValueError(
            f"行情缺失或未更新：{provider_symbol}，缺少{missing_dates}"
        )

    return [by_date[trading_date] for trading_date in expected_dates]


def save_daily_prices(prices, provider_symbol, output_dir, keep_count,expected_dates,):
    """
    保存最近指定数量的日线，完成写入后替换正式文件。

    :param prices: 已按日期升序排列的行情列表
    :param provider_symbol: 腾讯股票代码，例如usAAPL.OQ
    :param output_dir: 输出目录绝对路径
    :param keep_count: 保留的日线数量
    :return: CSV文件绝对路径
    """
    if not os.path.isabs(output_dir):
        raise ValueError("输出目录必须使用绝对路径")
    if keep_count <= 0 or len(prices) < keep_count:
        raise ValueError(f"日线数量不足：需要{keep_count}条，实际{len(prices)}条")
    if not provider_symbol.startswith("us") or "." not in provider_symbol:
        raise ValueError(f"不支持的股票代码：{provider_symbol}")
    if len(expected_dates) != keep_count:
        raise ValueError("预期交易日数量与保存数量不一致")

    prices = select_trading_window(
        prices, provider_symbol, expected_dates,
    )

    # 去掉市场前缀和最后一个交易所后缀，保留股票自身的点号。
    symbol = provider_symbol[2:].rsplit(".", 1)[0]
    output_path = os.path.join(output_dir, f"{symbol}.csv")
    os.makedirs(output_dir, exist_ok=True)
    fieldnames = ["symbol", "date", "open", "high", "low", "close", "volume"]
    temporary_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="utf-8-sig",
            newline="",
            dir=output_dir,
            suffix=".tmp",
            delete=False,
        ) as output_file:
            temporary_path = output_file.name
            writer = csv.DictWriter(output_file, fieldnames=fieldnames)
            writer.writeheader()
            for price in prices[-keep_count:]:
                writer.writerow({**price, "symbol": symbol})
        os.replace(temporary_path, output_path)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)
    return output_path


def resolve_tencent_symbol(symbol):
    """
    查询腾讯搜索接口，精确匹配标准美股代码。

    :param symbol: 标准代码，例如AAPL、SPY、BRK.B
    :return: 腾讯行情代码，例如usAAPL.OQ
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("股票代码不能为空")

    query = urllib.parse.urlencode({"t": "all", "q": symbol})
    request = urllib.request.Request(
        f"{TENCENT_SYMBOL_SEARCH_URL}?{query}",
        headers={"User-Agent": "Mozilla/5.0"},
    )
    with urllib.request.urlopen(
        request, timeout=REQUEST_TIMEOUT_SECONDS,
    ) as response:
        content = response.read().decode("utf-8-sig")

    # 只解析返回的字符串，不执行接口返回的JavaScript。
    match = re.search(
        r'v_hint\s*=\s*("(?:\\.|[^"\\])*")',
        content,
    )
    if not match:
        raise RuntimeError(f"证券搜索响应格式异常：{symbol}")

    hints = json.loads(match.group(1))
    candidates = set()
    for item in hints.split("^"):
        parts = item.split("~")
        if len(parts) < 2 or parts[0] != "us":
            continue
        provider_code = parts[1].upper()
        standard_code = provider_code.rsplit(".", 1)[0]
        if standard_code == symbol:
            candidates.add("us" + provider_code)

    if not candidates:
        raise LookupError(f"腾讯未找到精确匹配的美股代码：{symbol}")
    if len(candidates) > 1:
        raise ValueError(f"腾讯代码匹配存在歧义：{symbol}，{sorted(candidates)}")
    return candidates.pop()