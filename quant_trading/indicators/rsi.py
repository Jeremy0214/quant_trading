"""
indicators/rsi.py
Relative Strength Index (RSI) using Wilder's smoothing (EWM).

Added columns
─────────────
RSI                 RSI value (0–100)
rsi_overbought      True when RSI > 70
rsi_oversold        True when RSI < 30
rsi_bullish_signal  RSI rising out of oversold territory
rsi_bearish_signal  RSI falling out of overbought territory
"""

import pandas as pd

from config import RSI_PERIOD, RSI_OVERBOUGHT, RSI_OVERSOLD


def _calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    # Wilder smoothing (equivalent to EMA with com = period-1)
    avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()

    rs  = avg_gain / avg_loss.replace(0, float("nan"))
    rsi = 100 - (100 / (1 + rs))
    return rsi


def add_rsi(df: pd.DataFrame) -> pd.DataFrame:
    df["RSI"] = _calc_rsi(df["close"])

    df["rsi_overbought"] = df["RSI"] > RSI_OVERBOUGHT
    df["rsi_oversold"]   = df["RSI"] < RSI_OVERSOLD

    # Signal: RSI crosses back above oversold / below overbought
    df["rsi_bullish_signal"] = (df["RSI"] > RSI_OVERSOLD) & (df["RSI"].shift(1) <= RSI_OVERSOLD)
    df["rsi_bearish_signal"] = (df["RSI"] < RSI_OVERBOUGHT) & (df["RSI"].shift(1) >= RSI_OVERBOUGHT)

    return df
