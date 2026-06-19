"""
indicators/fvg.py
Fair Value Gap (FVG) / Imbalance detection.

Definition (3-candle pattern: C1, C2, C3)
──────────────────────────────────────────
Bullish FVG : C1.high < C3.low   → gap = [C1.high, C3.low]   (tagged on C2)
Bearish FVG : C1.low  > C3.high  → gap = [C3.high, C1.low]   (tagged on C2)

"Filled" means price later re-entered the gap zone.

Added columns
─────────────
fvg_bullish         True at C2 of a bullish FVG
fvg_bull_top        Top    of the bullish gap  (C3.low)
fvg_bull_bottom     Bottom of the bullish gap  (C1.high)
fvg_bull_filled     True when a future candle has  low <= fvg_bull_top
fvg_bearish         True at C2 of a bearish FVG
fvg_bear_top        Top    of the bearish gap  (C1.low)
fvg_bear_bottom     Bottom of the bearish gap  (C3.high)
fvg_bear_filled     True when a future candle has high >= fvg_bear_bottom
"""

import numpy as np
import pandas as pd


def detect_fvg(df: pd.DataFrame) -> pd.DataFrame:
    n     = len(df)
    highs = df["high"].values
    lows  = df["low"].values

    fvg_bull        = np.zeros(n, dtype=bool)
    fvg_bull_top    = np.full(n, np.nan)
    fvg_bull_bot    = np.full(n, np.nan)
    fvg_bear        = np.zeros(n, dtype=bool)
    fvg_bear_top    = np.full(n, np.nan)
    fvg_bear_bot    = np.full(n, np.nan)

    # Detect gaps (C2 is index i, C1 = i-1, C3 = i+1)
    for i in range(1, n - 1):
        c1_high = highs[i - 1]
        c1_low  = lows[i - 1]
        c3_high = highs[i + 1]
        c3_low  = lows[i + 1]

        if c1_high < c3_low:                      # Bullish FVG
            fvg_bull[i]     = True
            fvg_bull_top[i] = c3_low
            fvg_bull_bot[i] = c1_high

        if c1_low > c3_high:                      # Bearish FVG
            fvg_bear[i]     = True
            fvg_bear_top[i] = c1_low
            fvg_bear_bot[i] = c3_high

    df["fvg_bullish"]     = fvg_bull
    df["fvg_bull_top"]    = fvg_bull_top
    df["fvg_bull_bottom"] = fvg_bull_bot
    df["fvg_bearish"]     = fvg_bear
    df["fvg_bear_top"]    = fvg_bear_top
    df["fvg_bear_bottom"] = fvg_bear_bot

    # ── Fill detection ────────────────────────────────────────────────────────
    # Build cumulative min of 'low' and max of 'high' from the END so we can
    # determine, for each bar i, whether any bar j > i has low <= threshold.

    # Vectorised: for each bullish FVG bar, find the minimum low after it.
    # We use a reversed cumulative minimum shifted by 1.
    rev_min_low  = df["low"][::-1].cummin()[::-1].shift(-1)   # min(low[i+1:])
    rev_max_high = df["high"][::-1].cummax()[::-1].shift(-1)   # max(high[i+1:])

    bull_filled = fvg_bull & (rev_min_low <= df["fvg_bull_top"])
    bear_filled = fvg_bear & (rev_max_high >= df["fvg_bear_bottom"])

    df["fvg_bull_filled"] = bull_filled.fillna(False)
    df["fvg_bear_filled"] = bear_filled.fillna(False)

    return df
