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


# ── 5. Active OB Zone Tracking ────────────────────────────────────────────────

def _track_active_obs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Forward-fill the most recently formed OB zone until price closes through it
    (violation).  Two independent cursors are maintained — one for each side.

    Violation rules
    ───────────────
    Bullish OB violated : close < ob_low  (price closes below the zone)
    Bearish OB violated : close > ob_high (price closes above the zone)

    Added columns
    ─────────────
    active_ob_bull_high / active_ob_bull_low  — last unviolated bullish OB bounds
    active_ob_bear_high / active_ob_bear_low  — last unviolated bearish OB bounds
    """
    n      = len(df)
    closes = df["close"].values

    ob_bull_h = df["ob_bullish_high"].values
    ob_bull_l = df["ob_bullish_low"].values
    ob_bear_h = df["ob_bearish_high"].values
    ob_bear_l = df["ob_bearish_low"].values

    act_bull_h = np.full(n, np.nan)
    act_bull_l = np.full(n, np.nan)
    act_bear_h = np.full(n, np.nan)
    act_bear_l = np.full(n, np.nan)

    curr_bull_h = curr_bull_l = np.nan
    curr_bear_h = curr_bear_l = np.nan

    for i in range(n):
        # New OB formed at this bar — update cursor
        if not np.isnan(ob_bull_h[i]):
            curr_bull_h = ob_bull_h[i]
            curr_bull_l = ob_bull_l[i]
        if not np.isnan(ob_bear_h[i]):
            curr_bear_h = ob_bear_h[i]
            curr_bear_l = ob_bear_l[i]

        # Violation check
        if not np.isnan(curr_bull_l) and closes[i] < curr_bull_l:
            curr_bull_h = curr_bull_l = np.nan
        if not np.isnan(curr_bear_h) and closes[i] > curr_bear_h:
            curr_bear_h = curr_bear_l = np.nan

        act_bull_h[i] = curr_bull_h
        act_bull_l[i] = curr_bull_l
        act_bear_h[i] = curr_bear_h
        act_bear_l[i] = curr_bear_l

    df["active_ob_bull_high"] = act_bull_h
    df["active_ob_bull_low"]  = act_bull_l
    df["active_ob_bear_high"] = act_bear_h
    df["active_ob_bear_low"]  = act_bear_l
    return df


# ── 6. Propulsion Block (PB) Detection ───────────────────────────────────────

def _detect_propulsion_blocks(df: pd.DataFrame) -> pd.DataFrame:
    """
    Propulsion Block (PB): the overlap zone between an active bullish OB and
    an active bearish OB.  When price enters this confluence zone it signals
    a high-probability **reversal** (counter-trend trade opportunity).

    Entry triggers
    ──────────────
    pb_bearish : price enters PB from below  → SHORT reversal signal
    pb_bullish : price enters PB from above  → LONG  reversal signal

    Added columns
    ─────────────
    pb_zone_high   top    of the PB overlap zone (NaN when none exists)
    pb_zone_low    bottom of the PB overlap zone (NaN when none exists)
    pb_bearish     True on the bar price first enters PB from below (→ short)
    pb_bullish     True on the bar price first enters PB from above (→ long)
    """
    act_bull_h = df["active_ob_bull_high"].values
    act_bull_l = df["active_ob_bull_low"].values
    act_bear_h = df["active_ob_bear_high"].values
    act_bear_l = df["active_ob_bear_low"].values
    closes     = df["close"].values
    n          = len(df)

    pb_high = np.full(n, np.nan)
    pb_low  = np.full(n, np.nan)
    pb_bear = np.zeros(n, dtype=bool)
    pb_bull = np.zeros(n, dtype=bool)

    for i in range(1, n):
        bh = act_bull_h[i]; bl = act_bull_l[i]
        eh = act_bear_h[i]; el = act_bear_l[i]

        if np.isnan(bh) or np.isnan(eh):
            continue

        overlap_low  = max(bl, el)
        overlap_high = min(bh, eh)
        if overlap_high <= overlap_low:          # no real overlap
            continue

        pb_high[i] = overlap_high
        pb_low[i]  = overlap_low

        prev = closes[i - 1]
        curr = closes[i]

        # Price enters PB from below → bears can take over (short signal)
        if prev < overlap_low and curr >= overlap_low:
            pb_bear[i] = True
        # Price enters PB from above → bulls can take over (long signal)
        elif prev > overlap_high and curr <= overlap_high:
            pb_bull[i] = True

    df["pb_zone_high"] = pb_high
    df["pb_zone_low"]  = pb_low
    df["pb_bearish"]   = pb_bear
    df["pb_bullish"]   = pb_bull
    return df


# ── 7. Liquidity Sweep (Stop Hunt) Detection ─────────────────────────────────

def _detect_liquidity_sweep(df: pd.DataFrame) -> pd.DataFrame:
    """
    Detect stop-hunt / liquidity-grab candles.

    Bullish sweep : candle wick dips below the last confirmed swing-low
                    but the close recovers ABOVE it  → sell-side liquidity swept,
                    reversal upward likely.
    Bearish sweep : candle wick spikes above the last confirmed swing-high
                    but the close retreats BELOW it  → buy-side liquidity swept,
                    reversal downward likely.

    Added columns
    ─────────────
    liq_sweep_bull   True on a bullish liquidity-sweep candle
    liq_sweep_bear   True on a bearish liquidity-sweep candle
    """
    last_sl = df["low"].where(df["swing_low"]).ffill().shift(1)
    last_sh = df["high"].where(df["swing_high"]).ffill().shift(1)

    df["liq_sweep_bull"] = (df["low"] < last_sl) & (df["close"] > last_sl)
    df["liq_sweep_bear"] = (df["high"] > last_sh) & (df["close"] < last_sh)
    return df


# ── 8. Premium / Discount Zone Classification ────────────────────────────────

def _detect_premium_discount(df: pd.DataFrame, length: int) -> pd.DataFrame:
    """
    Classify each bar relative to the most recent swing range.

    equilibrium = 50 % of [range_low .. range_high]
    discount    = close < equilibrium  (favourable for longs)
    premium     = close > equilibrium  (favourable for shorts)

    Added columns
    ─────────────
    range_high    rolling swing high over `length` bars
    range_low     rolling swing low  over `length` bars
    equilibrium   mid-point of the range
    in_discount   True when close < equilibrium
    in_premium    True when close > equilibrium
    """
    range_high = df["high"].rolling(length, min_periods=1).max()
    range_low  = df["low"].rolling(length, min_periods=1).min()
    equil      = (range_high + range_low) / 2

    df["range_high"]  = range_high
    df["range_low"]   = range_low
    df["equilibrium"] = equil
    df["in_discount"] = df["close"] < equil
    df["in_premium"]  = df["close"] > equil
    return df


# ── Public entry point ────────────────────────────────────────────────────────

def add_smc(df: pd.DataFrame, length: int = SMC_SWING_LENGTH) -> pd.DataFrame:
    df = _find_swing_highs_lows(df, length)
    df = _detect_bos(df)
    df = _detect_choch(df)
    df = _detect_order_blocks(df, length)
    df = _track_active_obs(df)
    df = _detect_propulsion_blocks(df)
    df = _detect_liquidity_sweep(df)
    df = _detect_premium_discount(df, length)
    return df
