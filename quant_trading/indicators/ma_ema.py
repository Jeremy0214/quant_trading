"""
indicators/ma_ema.py
Simple Moving Average (MA) and Exponential Moving Average (EMA).

Added columns
─────────────
EMA_<SHORT>   short-period EMA (default 20)
EMA_<LONG>    long-period EMA  (default 50)
EMA_<TREND>   trend EMA        (default 200)
MA_<SHORT>    simple MA (20)
MA_<LONG>     simple MA (50)
ema_bullish   True on the bar where EMA_SHORT crosses above EMA_LONG
ema_bearish   True on the bar where EMA_SHORT crosses below EMA_LONG
trend_up      close > EMA_200
trend_down    close < EMA_200
"""

import pandas as pd

from config import EMA_SHORT, EMA_LONG, EMA_TREND, EMA_FILTER


def _sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period, min_periods=period).mean()


def _ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def add_ma_ema(df: pd.DataFrame) -> pd.DataFrame:
    df[f"EMA_{EMA_SHORT}"]  = _ema(df["close"], EMA_SHORT)
    df[f"EMA_{EMA_LONG}"]   = _ema(df["close"], EMA_LONG)
    df[f"EMA_{EMA_TREND}"]  = _ema(df["close"], EMA_TREND)
    df[f"EMA_{EMA_FILTER}"] = _ema(df["close"], EMA_FILTER)   # directional bias (56)
    df[f"MA_{EMA_SHORT}"]   = _sma(df["close"], EMA_SHORT)
    df[f"MA_{EMA_LONG}"]    = _sma(df["close"], EMA_LONG)

    # Golden / Death cross signals
    above = df[f"EMA_{EMA_SHORT}"] > df[f"EMA_{EMA_LONG}"]
    df["ema_bullish"] = above & ~above.shift(1).fillna(False)
    df["ema_bearish"] = ~above & above.shift(1).fillna(False)

    # Overall trend direction
    df["trend_up"]   = df["close"] > df[f"EMA_{EMA_TREND}"]
    df["trend_down"]  = df["close"] < df[f"EMA_{EMA_TREND}"]

    return df
