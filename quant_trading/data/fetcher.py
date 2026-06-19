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

    Returns a DataFrame with columns:
        open, high, low, close, volume
    and a DatetimeIndex (UTC).
    """
    exchange = getattr(ccxt, EXCHANGE)({"enableRateLimit": True})

    raw = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    df = pd.DataFrame(raw, columns=["timestamp", "open", "high", "low", "close", "volume"])
    df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True)
    df.set_index("timestamp", inplace=True)
    df = df.astype(float)
    return df
