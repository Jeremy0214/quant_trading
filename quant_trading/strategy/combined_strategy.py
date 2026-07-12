"""
strategy/combined_strategy.py
Strategy v5.0 - SMC Enhanced: EMA-56 Bias + OB/PB Reversal + Dual TP
=======================================================================

Architecture
============

Signal A - Trend-Following (direction determined by EMA 56)
------------------------------------------------------------
  1. EMA 56 direction filter
       close > EMA 56 -> long only
       close < EMA 56 -> short only
  2. Market structure: BOS / MSS / CHoCH in trade direction
  3. Order Block (OB) retest entry
  4. Premium / Discount zone (buy discount, sell premium)
  5. SMC confluence: FVG or liquidity sweep
  6. EMA momentum (EMA 20 vs EMA 50)
  7. RSI + volume filters

Signal B - Propulsion Block Reversal (PB)
------------------------------------------
  When active bullish OB and active bearish OB overlap -> PB zone.
  Price entering the PB zone triggers a counter-trend signal:
       In uptrend (> EMA 56) -> PB fires SHORT signal
       In downtrend (< EMA 56) -> PB fires LONG signal

  Stop-Loss:
       PB SHORT SL = highest point of merged OB zone + ATR buffer
       PB LONG  SL = lowest  point of merged OB zone - ATR buffer

Dual Take-Profit
----------------
  TP1 = entry +/- risk * TP1_RR  (1:1)
  TP2 = entry +/- risk * TP2_RR  (1:2)

Output columns
--------------
  signal          1=LONG  -1=SHORT  0=no signal
  signal_type     "TREND" | "PB"
  signal_strength 0-5 quality score (for Discord display)
  sl_price        stop-loss price
  tp1_price       first take-profit (1:1)
  tp2_price       second take-profit (1:2)
  tp_price        alias for tp1_price (backward compat)
"""

import numpy as np
import pandas as pd

import config
from config import EMA_SHORT, EMA_LONG, EMA_FILTER

ATR_PERIOD = 14


def _rolling_any(series: pd.Series, window: int) -> pd.Series:
    """True if any value in the trailing window is truthy."""
    return series.astype(int).rolling(window, min_periods=1).max().astype(bool)


def _calc_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> pd.Series:
    hl  = df["high"] - df["low"]
    hpc = (df["high"] - df["close"].shift()).abs()
    lpc = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def generate_signals(
    df: pd.DataFrame,
    htf_trend: "pd.Series | None" = None,
) -> pd.DataFrame:
    """
    Generate SMC-enhanced signals with dual take-profit levels.

    Parameters
    ----------
    df        : DataFrame produced by the full indicator pipeline
                (add_ma_ema -> add_rsi -> add_smc -> detect_fvg).
    htf_trend : Optional higher-timeframe EMA_TREND trend (True = bullish).
    """
    df    = df.copy()
    close = df["close"]
    high  = df["high"]
    low   = df["low"]
    rsi   = df["RSI"]
    atr   = _calc_atr(df)
    vol_ma = df["volume"].rolling(config.VOL_MA_PERIOD, min_periods=1).mean()

    ema_s      = df[f"EMA_{EMA_SHORT}"]    # EMA 20
    ema_l      = df[f"EMA_{EMA_LONG}"]     # EMA 50
    ema_filter = df[f"EMA_{EMA_FILTER}"]   # EMA 56 - directional bias

    pb_look = config.PULLBACK_LOOKBACK

    # -- Directional bias: EMA 56 -------------------------------------------------
    # Above EMA 56 -> long-only mode; below -> short-only mode
    bias_long  = close > ema_filter
    bias_short = close < ema_filter

    # -- EMA momentum alignment ---------------------------------------------------
    ema_momentum_up = ema_s > ema_l
    ema_momentum_dn = ema_s < ema_l

    # -- Market structure: BOS or CHoCH (MSS) in trade direction -----------------
    structure_bull = df["bos_bullish"] | df["choch_bullish"]
    structure_bear = df["bos_bearish"] | df["choch_bearish"]
    structure_bull_recent = _rolling_any(structure_bull, pb_look)
    structure_bear_recent = _rolling_any(structure_bear, pb_look)

    # -- Active OB zone test ------------------------------------------------------
    act_bull_h = df["active_ob_bull_high"]
    act_bull_l = df["active_ob_bull_low"]
    act_bear_h = df["active_ob_bear_high"]
    act_bear_l = df["active_ob_bear_low"]

    # Price inside active bullish OB zone
    in_bull_ob = (
        act_bull_h.notna()
        & (close >= act_bull_l)
        & (close <= act_bull_h)
    )
    # Price inside active bearish OB zone
    in_bear_ob = (
        act_bear_h.notna()
        & (close >= act_bear_l)
        & (close <= act_bear_h)
    )

    # -- Premium / Discount zone --------------------------------------------------
    in_discount = df["in_discount"]   # below equilibrium -> favour longs
    in_premium  = df["in_premium"]    # above equilibrium -> favour shorts

    # -- Liquidity sweep confluence -----------------------------------------------
    liq_bull_recent = _rolling_any(df["liq_sweep_bull"], pb_look)
    liq_bear_recent = _rolling_any(df["liq_sweep_bear"], pb_look)

    # -- FVG confluence -----------------------------------------------------------
    fvg_bull_active = df["fvg_bullish"] & ~df["fvg_bull_filled"]
    fvg_bear_active = df["fvg_bearish"] & ~df["fvg_bear_filled"]
    fvg_bull_recent = _rolling_any(fvg_bull_active, pb_look)
    fvg_bear_recent = _rolling_any(fvg_bear_active, pb_look)

    # FVG or liquidity sweep as SMC confluence (at least one required)
    smc_conf_long  = fvg_bull_recent | liq_bull_recent
    smc_conf_short = fvg_bear_recent | liq_bear_recent

    # -- RSI filters --------------------------------------------------------------
    rsi_ok_long  = (rsi > config.RSI_TRIGGER_LONG)  & (rsi < config.RSI_MAX_LONG)
    rsi_ok_short = (rsi < config.RSI_TRIGGER_SHORT) & (rsi > config.RSI_MIN_SHORT)
    rsi_reset_l  = _rolling_any(rsi < config.RSI_PULLBACK_LONG,  pb_look)
    rsi_reset_s  = _rolling_any(rsi > config.RSI_PULLBACK_SHORT, pb_look)

    # -- Volume + extension filters -----------------------------------------------
    vol_ok       = df["volume"] > vol_ma * config.VOL_MULT
    ext_ok_long  = (close - ema_s) < atr * config.EXT_MAX_ATR
    ext_ok_short = (ema_s - close) < atr * config.EXT_MAX_ATR

    # =============================================================================
    # Signal A: Trend-Following
    # All layers must be satisfied simultaneously.
    # =============================================================================
    trend_long_mask = (
        bias_long                    # L1: above EMA 56
        & ema_momentum_up            # L2: EMA 20 > EMA 50
        & structure_bull_recent      # L3: BOS/CHoCH bullish in window
        & in_bull_ob                 # L4: price retesting bullish OB
        & in_discount                # L5: price in discount zone
        & smc_conf_long              # L6: FVG or liquidity sweep
        & rsi_ok_long & rsi_reset_l  # L7: RSI momentum
        & vol_ok & ext_ok_long       # L8: volume + not overextended
    )

    trend_short_mask = (
        bias_short
        & ema_momentum_dn
        & structure_bear_recent
        & in_bear_ob
        & in_premium
        & smc_conf_short
        & rsi_ok_short & rsi_reset_s
        & vol_ok & ext_ok_short
    )

    if config.LONG_ONLY:
        trend_short_mask = pd.Series(False, index=df.index)

    # -- Optional HTF confluence --------------------------------------------------
    if htf_trend is not None:
        combined_idx = htf_trend.index.union(df.index)
        htf_aligned  = htf_trend.reindex(combined_idx).ffill().reindex(df.index)
        htf_up   = htf_aligned.fillna(False).astype(bool)
        htf_down = (~htf_aligned.fillna(True)).astype(bool)
        trend_long_mask  = trend_long_mask  & htf_up
        trend_short_mask = trend_short_mask & htf_down
        # PB reversal intentionally skips HTF confluence (it IS counter-trend)

    # =============================================================================
    # Signal B: Propulsion Block Reversal
    # PB short fires when above EMA 56 (reverses downward from PB zone).
    # PB long  fires when below EMA 56 (reverses upward  from PB zone).
    # =============================================================================
    pb_short_mask = df["pb_bearish"] & bias_long    # in uptrend -> reversal short
    pb_long_mask  = df["pb_bullish"] & bias_short   # in downtrend -> reversal long

    if config.LONG_ONLY:
        pb_short_mask = pd.Series(False, index=df.index)

    # =============================================================================
    # Stop-Loss Calculation
    # =============================================================================
    entry         = close
    swing_low_sl  = low.rolling(config.SL_SWING_LOOKBACK, min_periods=1).min()
    swing_high_sl = high.rolling(config.SL_SWING_LOOKBACK, min_periods=1).max()

    # Trend SL (structural swing + ATR buffer)
    raw_sl_long = swing_low_sl - atr * config.SL_ATR_BUFFER
    dist_long   = (entry - raw_sl_long).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_trend_long = entry - dist_long

    raw_sl_short = swing_high_sl + atr * config.SL_ATR_BUFFER
    dist_short   = (raw_sl_short - entry).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_trend_short = entry + dist_short

    # PB SL (highest/lowest point of the merged OB zone + ATR buffer)
    pb_zone_high = df["pb_zone_high"]
    pb_zone_low  = df["pb_zone_low"]

    # PB short: SL = top of merged OB zone + buffer
    raw_pb_sl_short = pb_zone_high + atr * config.SL_ATR_BUFFER
    dist_pb_short   = (raw_pb_sl_short - entry).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_pb_short = entry + dist_pb_short

    # PB long: SL = bottom of merged OB zone - buffer
    raw_pb_sl_long = pb_zone_low - atr * config.SL_ATR_BUFFER
    dist_pb_long   = (entry - raw_pb_sl_long).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_pb_long = entry - dist_pb_long

    # =============================================================================
    # Dual Take-Profit  (TP1 = 1:1, TP2 = 1:2)
    # =============================================================================
    tp1_trend_long  = entry + dist_long  * config.TP1_RR
    tp2_trend_long  = entry + dist_long  * config.TP2_RR
    tp1_trend_short = entry - dist_short * config.TP1_RR
    tp2_trend_short = entry - dist_short * config.TP2_RR

    tp1_pb_long  = entry + dist_pb_long  * config.TP1_RR
    tp2_pb_long  = entry + dist_pb_long  * config.TP2_RR
    tp1_pb_short = entry - dist_pb_short * config.TP1_RR
    tp2_pb_short = entry - dist_pb_short * config.TP2_RR

    # =============================================================================
    # Assemble output columns
    # =============================================================================
    df["signal"]          = 0
    df["signal_type"]     = ""
    df["signal_strength"] = 0
    df["sl_price"]        = np.nan
    df["tp1_price"]       = np.nan
    df["tp2_price"]       = np.nan

    # Signal A - Trend Long
    df.loc[trend_long_mask,  "signal"]      = 1
    df.loc[trend_long_mask,  "signal_type"] = "TREND"
    df.loc[trend_long_mask,  "sl_price"]    = sl_trend_long[trend_long_mask]
    df.loc[trend_long_mask,  "tp1_price"]   = tp1_trend_long[trend_long_mask]
    df.loc[trend_long_mask,  "tp2_price"]   = tp2_trend_long[trend_long_mask]

    # Signal A - Trend Short
    df.loc[trend_short_mask, "signal"]      = -1
    df.loc[trend_short_mask, "signal_type"] = "TREND"
    df.loc[trend_short_mask, "sl_price"]    = sl_trend_short[trend_short_mask]
    df.loc[trend_short_mask, "tp1_price"]   = tp1_trend_short[trend_short_mask]
    df.loc[trend_short_mask, "tp2_price"]   = tp2_trend_short[trend_short_mask]

    # Signal B - PB Long (overrides trend signal if both fire on same bar)
    df.loc[pb_long_mask, "signal"]      = 1
    df.loc[pb_long_mask, "signal_type"] = "PB"
    df.loc[pb_long_mask, "sl_price"]    = sl_pb_long[pb_long_mask]
    df.loc[pb_long_mask, "tp1_price"]   = tp1_pb_long[pb_long_mask]
    df.loc[pb_long_mask, "tp2_price"]   = tp2_pb_long[pb_long_mask]

    # Signal B - PB Short
    df.loc[pb_short_mask, "signal"]      = -1
    df.loc[pb_short_mask, "signal_type"] = "PB"
    df.loc[pb_short_mask, "sl_price"]    = sl_pb_short[pb_short_mask]
    df.loc[pb_short_mask, "tp1_price"]   = tp1_pb_short[pb_short_mask]
    df.loc[pb_short_mask, "tp2_price"]   = tp2_pb_short[pb_short_mask]

    # Backward-compat alias
    df["tp_price"] = df["tp1_price"]

    # -- Signal strength score (0-5) for Discord display -------------------------
    # Each direction uses only its own bullish/bearish components.
    strength_long = (
        structure_bull_recent.astype(int)
        + in_bull_ob.astype(int)
        + smc_conf_long.astype(int)
        + in_discount.astype(int)
        + vol_ok.astype(int)
    ).clip(upper=5)

    strength_short = (
        structure_bear_recent.astype(int)
        + in_bear_ob.astype(int)
        + smc_conf_short.astype(int)
        + in_premium.astype(int)
        + vol_ok.astype(int)
    ).clip(upper=5)

    long_sig_mask  = df["signal"] == 1
    short_sig_mask = df["signal"] == -1
    df.loc[long_sig_mask,  "signal_strength"] = strength_long[long_sig_mask]
    df.loc[short_sig_mask, "signal_strength"] = strength_short[short_sig_mask]

    # -- Safety: remove signals where SL ended up on the wrong side of entry -----
    bad = (df["signal"] != 0) & (
        ((df["signal"] == 1)  & (df["sl_price"] >= entry))
        | ((df["signal"] == -1) & (df["sl_price"] <= entry))
    )
    df.loc[bad, ["signal", "signal_strength"]] = 0
    df.loc[bad, "signal_type"]                 = ""
    df.loc[bad, ["sl_price", "tp1_price", "tp2_price", "tp_price"]] = np.nan

    return df