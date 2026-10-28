import logging
import os
import sqlite3
import time

from data_sources.tencent_daily import resolve_tencent_symbol
from contextlib import closing
from standard_module.config import (
    SYMBOL_CACHE_DB_PATH,
    SYMBOL_CACHE_TTL_DAYS,
)


def resolve_cached_symbol(symbol, force_refresh=False):
    """
    优先读取有效缓存，未命中时查询腾讯并保存成功结果。

    :param symbol: 标准股票代码，例如SPY、BRK.B
    :param force_refresh: 是否忽略缓存重新查询
    :return: 腾讯行情代码
    """
    symbol = symbol.strip().upper()
    if not symbol:
        raise ValueError("股票代码不能为空")
    if not os.path.isabs(SYMBOL_CACHE_DB_PATH):
        raise ValueError("映射缓存必须使用绝对路径")
    if SYMBOL_CACHE_TTL_DAYS <= 0:
        raise ValueError("映射缓存有效天数必须大于0")

    os.makedirs(os.path.dirname(SYMBOL_CACHE_DB_PATH), exist_ok=True)
    with closing(sqlite3.connect(SYMBOL_CACHE_DB_PATH)) as connection, connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS symbol_mapping (
                symbol TEXT PRIMARY KEY,
                provider_symbol TEXT NOT NULL,
                updated_at REAL NOT NULL
            )
            """
        )
        cached = connection.execute(
            """
            SELECT provider_symbol, updated_at
            FROM symbol_mapping
            WHERE symbol = ?
            """,
            (symbol,),
        ).fetchone()

        if cached and not force_refresh:
            age_seconds = time.time() - cached[1]
            if 0 <= age_seconds < SYMBOL_CACHE_TTL_DAYS * 86400:
                logging.info("命中代码缓存：%s → %s", symbol, cached[0])
                return cached[0]

        provider_symbol = resolve_tencent_symbol(symbol)
        connection.execute(
            """
            INSERT INTO symbol_mapping(symbol, provider_symbol, updated_at)
            VALUES (?, ?, ?)
            ON CONFLICT(symbol) DO UPDATE SET
                provider_symbol = excluded.provider_symbol,
                updated_at = excluded.updated_at
            """,
            (symbol, provider_symbol, time.time()),
        )

    logging.info("已更新代码缓存：%s → %s", symbol, provider_symbol)
    return provider_symbol