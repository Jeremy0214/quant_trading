"""
strategy/combined_strategy.py
Combined signal generation using EMA + RSI + SMC + FVG.

Signal Logic (vectorised, 6 conditions each direction)
───────────────────────────────────────────────────────
LONG  requires ≥ 4 / 6 conditions:
  1. close > EMA_200           (macro uptrend)
  2. EMA_20 > EMA_50           (short-term momentum up)
  3. RSI in (30, 55)           (not overbought; slight pullback)
  4. Recent bullish OB nearby  (SMC institutional support)
  5. Unfilled bullish FVG      (liquidity imbalance)
  6. Recent bullish BOS        (structure confirmation)

SHORT requires ≥ 4 / 6 conditions (mirror):
  1. close < EMA_200
  2. EMA_20 < EMA_50
  3. RSI in (45, 70)
  4. Recent bearish OB nearby
  5. Unfilled bearish FVG
  6. Recent bearish BOS

"Recent" = within the last LOOKBACK bars.

Added columns
─────────────
signal           1 = LONG, -1 = SHORT, 0 = no signal
signal_strength  number of confirming conditions (max 6)
long_score       raw long condition count
short_score      raw short condition count
"""

import pandas as pd

from config import EMA_SHORT, EMA_LONG, EMA_TREND, RSI_OVERBOUGHT, RSI_OVERSOLD

LOOKBACK = 20   # bars to look back for SMC / FVG events


def generate_signals(df: pd.DataFrame) -> pd.DataFrame:
    def _rolling_any(series: pd.Series, window: int) -> pd.Series:
        """True if any value in the rolling window is True."""
        return series.astype(int).rolling(window, min_periods=1).max().astype(bool)

    # ── SMC / FVG proximity flags ─────────────────────────────────────────────
    recent_bull_ob  = _rolling_any(df["ob_bullish"],  LOOKBACK)
    recent_bear_ob  = _rolling_any(df["ob_bearish"],  LOOKBACK)
    recent_bos_bull = _rolling_any(df["bos_bullish"], LOOKBACK)
    recent_bos_bear = _rolling_any(df["bos_bearish"], LOOKBACK)

    unfilled_bull_fvg = df["fvg_bullish"] & ~df["fvg_bull_filled"]
    unfilled_bear_fvg = df["fvg_bearish"] & ~df["fvg_bear_filled"]
    recent_bull_fvg   = _rolling_any(unfilled_bull_fvg, LOOKBACK)
    recent_bear_fvg   = _rolling_any(unfilled_bear_fvg, LOOKBACK)

    # ── EMA conditions ────────────────────────────────────────────────────────
    ema_trend_up   = df["trend_up"]
    ema_trend_down = df["trend_down"]
    ema_mom_up     = df[f"EMA_{EMA_SHORT}"] > df[f"EMA_{EMA_LONG}"]
    ema_mom_down   = df[f"EMA_{EMA_SHORT}"] < df[f"EMA_{EMA_LONG}"]

    # ── RSI conditions ────────────────────────────────────────────────────────
    rsi_long  = (df["RSI"] > RSI_OVERSOLD) & (df["RSI"] < 55)
    rsi_short = (df["RSI"] < RSI_OVERBOUGHT) & (df["RSI"] > 45)

    # ── Score ─────────────────────────────────────────────────────────────────
    long_score = (
        ema_trend_up.astype(int)
        + ema_mom_up.astype(int)
        + rsi_long.astype(int)
        + recent_bull_ob.astype(int)
        + recent_bull_fvg.astype(int)
        + recent_bos_bull.astype(int)
    )

    short_score = (
        ema_trend_down.astype(int)
        + ema_mom_down.astype(int)
        + rsi_short.astype(int)
        + recent_bear_ob.astype(int)
        + recent_bear_fvg.astype(int)
        + recent_bos_bear.astype(int)
    )

    df["long_score"]  = long_score
    df["short_score"] = short_score

    # Require ≥ 4 conditions and strictly higher score than the opposite side
    long_mask  = (long_score  >= 4) & (long_score  > short_score)
    short_mask = (short_score >= 4) & (short_score > long_score)

    df["signal"]          = 0
    df["signal_strength"] = 0
    df.loc[long_mask,  "signal"]          = 1
    df.loc[short_mask, "signal"]          = -1
    df.loc[long_mask,  "signal_strength"] = long_score[long_mask]
    df.loc[short_mask, "signal_strength"] = short_score[short_mask]

    return df
