import csv
import io
import os
import tempfile
import urllib.request
import logging
import time
import urllib.error

from standard_module.config import (
    NASDAQ_LISTED_URL,
    OTHER_LISTED_URL,
    REQUEST_TIMEOUT_SECONDS,
    UNIVERSE_OUTPUT_PATH,
    BATCH_MAX_ATTEMPTS,
    BATCH_RETRY_SECONDS,
)


def fetch_directory(url, symbol_field, default_exchange):
    """
    下载一份官方证券目录，排除测试证券和文件尾说明。

    :param url: 目录下载地址
    :param symbol_field: 该目录中的证券代码字段
    :param default_exchange: 默认交易所，为空时使用目录中的Exchange字段
    :return: 标准化证券记录列表，包含ETF及其他证券类型
    """
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0"},
    )
    for attempt in range(1, BATCH_MAX_ATTEMPTS + 1):
        try:
            with urllib.request.urlopen(
                request, timeout=REQUEST_TIMEOUT_SECONDS,
            ) as response:
                content = response.read().decode("utf-8-sig")
            break
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt >= BATCH_MAX_ATTEMPTS:
                raise
            logging.warning(
                "证券名单下载失败，%s秒后重试：%s/%s，地址：%s",
                BATCH_RETRY_SECONDS,
                attempt,
                BATCH_MAX_ATTEMPTS,
                url,
            )
            time.sleep(BATCH_RETRY_SECONDS)

    reader = csv.DictReader(io.StringIO(content), delimiter="|")
    required = {symbol_field, "Security Name", "Test Issue", "ETF"}
    if not default_exchange:
        required.add("Exchange")
    if not required.issubset(reader.fieldnames or []):
        raise ValueError("证券目录缺少必要字段，停止更新")

    records = []
    for row in reader:
        symbol = (row.get(symbol_field) or "").strip()
        if not symbol or symbol.startswith("File Creation Time:"):
            continue
        if row.get("Test Issue") != "N":
            continue
        exchange = default_exchange or (row.get("Exchange") or "").strip()
        if not exchange or row.get("ETF") not in {"Y", "N"}:
            raise ValueError(f"证券目录字段异常：{symbol}")
        records.append({
            "symbol": symbol,
            "name": row["Security Name"].strip(),
            "exchange": exchange,
            "is_etf": row["ETF"],
        })

    if not records:
        raise RuntimeError("证券目录为空，停止更新")
    return records


def save_stock_universe():
    """
    合并官方证券目录，完成写入后替换正式名单。

    :return: 输出文件绝对路径及记录数量
    """
    records = fetch_directory(NASDAQ_LISTED_URL, "Symbol", "NASDAQ")
    records.extend(fetch_directory(OTHER_LISTED_URL, "ACT Symbol", ""))

    # 交易所和代码共同标识一条目录记录，避免静默覆盖冲突。
    unique_records = {}
    for record in records:
        key = (record["exchange"], record["symbol"])
        if key in unique_records and unique_records[key] != record:
            raise ValueError(f"证券目录存在冲突：{key}")
        unique_records[key] = record
    records = sorted(
        unique_records.values(),
        key=lambda record: (record["symbol"], record["exchange"]),
    )

    output_dir = os.path.dirname(UNIVERSE_OUTPUT_PATH)
    os.makedirs(output_dir, exist_ok=True)
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
            writer = csv.DictWriter(
                output_file,
                fieldnames=["symbol", "name", "exchange", "is_etf"],
            )
            writer.writeheader()
            writer.writerows(records)
        os.replace(temporary_path, UNIVERSE_OUTPUT_PATH)
    finally:
        if temporary_path and os.path.exists(temporary_path):
            os.remove(temporary_path)

    return UNIVERSE_OUTPUT_PATH, len(records)