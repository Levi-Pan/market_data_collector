#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/27 13:31
# software:Vscode
# brief : 腾讯日线采集配置

import os


TENCENT_KLINE_URL = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
REQUEST_TIMEOUT_SECONDS = 20
REQUEST_BAR_COUNT = 45

# 第一阶段仅用于验证接口
# PRICE_TEST_SYMBOL = "usAAPL.OQ"
# PRICE_TEST_SYMBOL = "usMSFT.OQ"  # 微软
# PRICE_TEST_SYMBOL = "usIBM.N"    # IBM，注意后缀是 .N

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DAILY_OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "us_daily")
SAVE_BAR_COUNT = 30

NASDAQ_LISTED_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/nasdaqlisted.txt"
)
OTHER_LISTED_URL = (
    "https://www.nasdaqtrader.com/dynamic/SymDir/otherlisted.txt"
)
UNIVERSE_OUTPUT_PATH = os.path.join(PROJECT_DIR, "output", "universe.csv")

TENCENT_SYMBOL_SEARCH_URL = "https://smartbox.gtimg.cn/s3/"

PRICE_TEST_SYMBOL = "SPY"

MARKET_CALENDAR_NAME = "NYSE"
CALENDAR_LOOKBACK_DAYS = 120
MARKET_CLOSE_DELAY_MINUTES = 5

SYMBOL_CACHE_DB_PATH = os.path.join(PROJECT_DIR, "output", "symbol_mapping.sqlite3")
SYMBOL_CACHE_TTL_DAYS = 30
BATCH_SYMBOL_LIMIT = 0
BATCH_SLEEP_SECONDS = 1.0
BATCH_MAX_ATTEMPTS = 2
BATCH_RETRY_SECONDS = 5

BATCH_STATE_PATH = os.path.join(PROJECT_DIR, "output", "batch_state.json")

MASSIVE_API_KEY = "CEMba1lJbjlzKBS_tM3y3Y8RjlQ151gs"
MASSIVE_API_URL = "https://api.massive.com"
MASSIVE_TIMEOUT_SECONDS = 180

MASSIVE_OUTPUT_DIR = os.path.join(PROJECT_DIR, "output", "massive")
MASSIVE_REQUEST_INTERVAL_SECONDS = 13
MASSIVE_MAX_ATTEMPTS = 3

MASSIVE_KEEP_BATCHES = 2