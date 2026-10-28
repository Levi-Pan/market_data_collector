#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/27 13:31
# software:Vscode
# brief : 单只股票日线采集测试入口

import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)
from data_sources.trading_calendar import get_completed_trading_dates
from data_sources.symbol_cache import resolve_cached_symbol
from data_sources.tencent_daily import fetch_daily_prices, save_daily_prices
from standard_module.config import (DAILY_OUTPUT_DIR,PRICE_TEST_SYMBOL,REQUEST_BAR_COUNT,SAVE_BAR_COUNT,)


def main():
    """
    获取已收盘交易日，采集并保存完整行情窗口。

    :return: 无
    """
    expected_dates = get_completed_trading_dates(SAVE_BAR_COUNT)
    logging.info(
        "目标交易日：%s至%s",
        expected_dates[0], expected_dates[-1],
    )

    provider_symbol = resolve_cached_symbol(PRICE_TEST_SYMBOL)
    prices = fetch_daily_prices(provider_symbol, REQUEST_BAR_COUNT)
    output_path = save_daily_prices(
        prices,
        provider_symbol,
        DAILY_OUTPUT_DIR,
        SAVE_BAR_COUNT,
        expected_dates,
    )
    logging.info("已保存%s条日线：%s", SAVE_BAR_COUNT, output_path)

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        main()
    except Exception:
        logging.error("日线采集失败", exc_info=True)
        sys.exit(1)