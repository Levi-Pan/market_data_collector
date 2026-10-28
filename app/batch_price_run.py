#!/usr/bin/env python
# -*- coding:utf-8 -*-
# author:PZW
# datetime:2026/10/27 14:35
# software:Vscode
# brief : 小批量日线采集启动入口

import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_sources.batch_collector import run_batch_collection


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        sys.exit(run_batch_collection())
    except Exception:
        logging.error("批量采集无法完成", exc_info=True)
        sys.exit(1)