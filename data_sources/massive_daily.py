#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/29 13:03
# software:Vscode
# brief : 获取Massive指定交易日的美股全市场日线

import urllib.error
import urllib.request
import json
from datetime import date

from standard_module.config import (
    MASSIVE_API_KEY,
    MASSIVE_API_URL,
    MASSIVE_TIMEOUT_SECONDS,
)


def fetch_market_daily(trading_date):
    """
    获取指定交易日的美股日线，不包含OTC证券。

    :param trading_date: 交易日期，格式YYYY-MM-DD
    :return: Massive原始日线记录列表
    """
    trading_date = date.fromisoformat(trading_date).isoformat()
    if not MASSIVE_API_KEY:
        raise ValueError("请设置环境变量MASSIVE_API_KEY")

    url = (
        f"{MASSIVE_API_URL}/v2/aggs/grouped/locale/us/"
        f"market/stocks/{trading_date}"
        "?adjusted=true&include_otc=false"
    )
    request = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {MASSIVE_API_KEY}",
            "Accept": "application/json",
            "User-Agent": "market-data-collector/1.0",
        },
    )
    try:
        with urllib.request.urlopen(
            request,
            timeout=MASSIVE_TIMEOUT_SECONDS,
        ) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        raise RuntimeError(
            f"Massive请求失败：日期={trading_date}，"
            f"HTTP状态={error.code}"
        ) from error

    if payload.get("status") != "OK":
        raise RuntimeError(
            f"Massive响应异常：{payload.get('status')}，"
            f"{payload.get('error') or payload.get('message')}"
        )
    if payload.get("adjusted") is not True:
        raise ValueError("Massive返回的复权标记与请求不一致")

    rows = payload.get("results")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"该日期未返回行情，停止更新：{trading_date}")

    required_fields = {"T", "o", "h", "l", "c", "v", "t"}
    symbols = set()
    for row in rows:
        if not isinstance(row, dict) or not required_fields.issubset(row):
            raise ValueError(f"日线字段不完整：{trading_date}")
        symbol = row["T"]
        if not isinstance(symbol, str) or not symbol.strip():
            raise ValueError("行情包含空证券代码")
        if symbol in symbols:
            raise ValueError(f"行情包含重复证券代码：{symbol}")
        symbols.add(symbol)

    return rows