"""
data/fetcher.py
Fetch OHLCV candle data from Binance via ccxt (no API key required for public data).
"""

import ccxt
import pandas as pd

from config import EXCHANGE, SYMBOL, TIMEFRAME, LIMIT


def fetch_ohlcv(
    symbol: str = SYMBOL,
    timeframe: str = TIMEFRAME,
    limit: int = LIMIT,
) -> pd.DataFrame:
    """
    Fetch historical OHLCV data from Binance.

    When ``limit`` exceeds a single request's cap (~1000 candles), the data is
    fetched in multiple paginated requests and stitched together so backtests
    can access enough history to produce a large trade sample.

    Returns a DataFrame with columns:
        open, high, low, close, volume
    and a DatetimeIndex (UTC).
    """
    exchange = getattr(ccxt, EXCHANGE)({"enableRateLimit": True})

    per_call = 1000  # Binance max candles per request
    if limit <= per_call:
        raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    else:
        raw = _fetch_paginated(exchange, symbol, timeframe, limit, per_call)

    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df = df[~df.index.duplicated(keep="first")].sort_index()
    df = df.astype(float)
    return df


def _fetch_paginated(exchange, symbol, timeframe, limit, per_call):
    """Walk backwards from now in `per_call`-sized pages until `limit` rows."""
    tf_ms = exchange.parse_timeframe(timeframe) * 1000
    now   = exchange.milliseconds()
    since = now - limit * tf_ms

    rows: list = []
    cursor = since
    while len(rows) < limit:
        batch = exchange.fetch_ohlcv(symbol, timeframe, since=cursor, limit=per_call)
        if not batch:
            break
        rows.extend(batch)
        next_cursor = batch[-1][0] + tf_ms
        if next_cursor <= cursor:
            break
        cursor = next_cursor
        if batch[-1][0] >= now - tf_ms:
            break
    return rows[-limit:]

