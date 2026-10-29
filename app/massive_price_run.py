#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/29 13:10
# software:Vscode
# brief : 启动Massive美股日线批量采集

import logging
import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_sources.massive_collector import run_market_collection


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        run_market_collection()
    except Exception:
        logging.error("Massive采集失败，未发布新批次", exc_info=True)
        sys.exit(1)