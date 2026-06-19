"""
indicators/smc.py
Smart Money Concepts (SMC) — core building blocks.

Steps
─────
1. Swing Highs / Swing Lows      (pivot detection)
2. Break of Structure (BOS)      (structural break)
3. Change of Character (CHoCH)   (first opposing structural break)
4. Order Blocks (OB)             (last opposing candle before a BOS)

Added columns
─────────────
swing_high          True at a confirmed swing-high pivot
swing_low           True at a confirmed swing-low pivot
bos_bullish         True when close breaks above the last swing-high  (BOS up)
bos_bearish         True when close breaks below the last swing-low   (BOS down)
choch_bullish       True on first bullish BOS after a bearish BOS
choch_bearish       True on first bearish BOS after a bullish BOS
ob_bullish          True at the last bearish candle before a bullish BOS
ob_bullish_high     High of the bullish order block candle
ob_bullish_low      Low  of the bullish order block candle
ob_bearish          True at the last bullish candle before a bearish BOS
ob_bearish_high     High of the bearish order block candle
ob_bearish_low      Low  of the bearish order block candle
"""

import numpy as np
import pandas as pd

from config import SMC_SWING_LENGTH


# ── 1. Swing Highs / Lows ────────────────────────────────────────────────────

def _find_swing_highs_lows(df: pd.DataFrame, length: int) -> pd.DataFrame:
    """
    A swing-high at bar i: df['high'][i] is strictly the highest value in the
    window [i-length, i+length].  Swing-low is the mirror.
    The last `length` candles cannot be confirmed yet (look-ahead required).
    """
    highs = df["high"].values
    lows  = df["low"].values
    n     = len(df)

    sh = np.zeros(n, dtype=bool)
    sl = np.zeros(n, dtype=bool)

    for i in range(length, n - length):
        window_h = highs[i - length : i + length + 1]
        window_l = lows[i - length : i + length + 1]
        if highs[i] == window_h.max():
            sh[i] = True
        if lows[i] == window_l.min():
            sl[i] = True

    df["swing_high"] = sh
    df["swing_low"]  = sl
    return df


# ── 2. Break of Structure ─────────────────────────────────────────────────────

def _detect_bos(df: pd.DataFrame) -> pd.DataFrame:
    """
    BOS Bullish : close crosses above the most-recent confirmed swing-high.
    BOS Bearish : close crosses below the most-recent confirmed swing-low.
    Uses forward-fill so 'last known swing level' is O(n).
    """
    # Forward-fill last swing-high / swing-low price
    last_sh = df["high"].where(df["swing_high"]).ffill().shift(1)
    last_sl = df["low"].where(df["swing_low"]).ffill().shift(1)

    prev_close = df["close"].shift(1)

    df["bos_bullish"] = (df["close"] > last_sh) & (prev_close <= last_sh)
    df["bos_bearish"] = (df["close"] < last_sl) & (prev_close >= last_sl)

    # Avoid tagging the swing candle itself
    df.loc[df["swing_high"], "bos_bullish"] = False
    df.loc[df["swing_low"],  "bos_bearish"] = False

    return df


# ── 3. Change of Character ────────────────────────────────────────────────────

def _detect_choch(df: pd.DataFrame) -> pd.DataFrame:
    """
    CHoCH Bullish : first bullish BOS after a bearish BOS  (structure flips up)
    CHoCH Bearish : first bearish BOS after a bullish BOS  (structure flips down)
    """
    last_bear_bos = df["bos_bearish"].cumsum()
    last_bull_bos = df["bos_bullish"].cumsum()

    # CHoCH bullish = bullish BOS that occurs after at least one bearish BOS
    df["choch_bullish"] = df["bos_bullish"] & (last_bear_bos.shift(1).fillna(0) > 0)
    df["choch_bearish"] = df["bos_bearish"] & (last_bull_bos.shift(1).fillna(0) > 0)

    return df


# ── 4. Order Blocks ───────────────────────────────────────────────────────────

def _detect_order_blocks(df: pd.DataFrame, length: int) -> pd.DataFrame:
    """
    Bullish OB : last BEARISH candle immediately before a bullish BOS.
    Bearish OB : last BULLISH candle immediately before a bearish BOS.
    Only search within `length` bars before the BOS bar.
    """
    n = len(df)
    ob_bull      = np.zeros(n, dtype=bool)
    ob_bull_high = np.full(n, np.nan)
    ob_bull_low  = np.full(n, np.nan)
    ob_bear      = np.zeros(n, dtype=bool)
    ob_bear_high = np.full(n, np.nan)
    ob_bear_low  = np.full(n, np.nan)

    closes = df["close"].values
    opens  = df["open"].values
    highs  = df["high"].values
    lows   = df["low"].values
    bos_b  = df["bos_bullish"].values
    bos_s  = df["bos_bearish"].values

    for i in range(length, n):
        if bos_b[i]:
            for j in range(i - 1, max(-1, i - length - 1), -1):
                if closes[j] < opens[j]:          # bearish candle → bullish OB
                    ob_bull[j]      = True
                    ob_bull_high[j] = highs[j]
                    ob_bull_low[j]  = lows[j]
                    break

        if bos_s[i]:
            for j in range(i - 1, max(-1, i - length - 1), -1):
                if closes[j] > opens[j]:          # bullish candle → bearish OB
                    ob_bear[j]      = True
                    ob_bear_high[j] = highs[j]
                    ob_bear_low[j]  = lows[j]
                    break

    df["ob_bullish"]      = ob_bull
    df["ob_bullish_high"] = ob_bull_high
    df["ob_bullish_low"]  = ob_bull_low
    df["ob_bearish"]      = ob_bear
    df["ob_bearish_high"] = ob_bear_high
    df["ob_bearish_low"]  = ob_bear_low

    return df


# ── Public entry point ────────────────────────────────────────────────────────

def add_smc(df: pd.DataFrame, length: int = SMC_SWING_LENGTH) -> pd.DataFrame:
    df = _find_swing_highs_lows(df, length)
    df = _detect_bos(df)
    df = _detect_choch(df)
    df = _detect_order_blocks(df, length)
    return df
