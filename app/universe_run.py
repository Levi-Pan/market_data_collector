import logging
import os
import sys


BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from data_sources.stock_universe import save_stock_universe


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    try:
        output_path, record_count = save_stock_universe()
        logging.info("已保存%s条证券记录：%s", record_count, output_path)
    except Exception:
        logging.error("证券名单更新失败", exc_info=True)
        sys.exit(1)