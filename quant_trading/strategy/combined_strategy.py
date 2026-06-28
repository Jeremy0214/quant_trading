"""
strategy/combined_strategy.py
Strategy v3.0 — Trend-Pullback Continuation with Structural SL/TP
================================================================

設計目標
────────
1. 提高勝率：只順「已確立的趨勢」方向交易，並等待「回調後動能回歸」才進場，
   避免追高殺低與逆勢交易（舊版逆勢做空導致勝率偏低）。
2. 止損(SL)有依據：以「市場結構」的近期擺動低/高點為錨點，再加 ATR 緩衝，
   而非固定點數。被掃損代表結構真正被破壞。
3. 止盈(TP)有依據：以「實際風險距離 × 風報比(RR_RATIO)」計算，確保 R:R ≥ 1.5。
   因此每筆交易的 SL/TP 都會隨結構與波動動態變化。

進場邏輯（多單；空單為鏡像）
──────────────────────────────
第一層 趨勢過濾（全部成立）
    close > EMA_200            （站上長期趨勢線）
    EMA_50 > EMA_200           （中期趨勢向上）
    EMA_20 > EMA_50            （短期動能向上）

第二層 回調 + 動能回歸（觸發進場）
    近 PULLBACK_LOOKBACK 根內曾回踩 EMA_20（low ≤ EMA_20）— 確認是「回調」而非追高
    且 近 PULLBACK_LOOKBACK 根內 RSI 曾跌破 RSI_PULLBACK_LONG — 確認動能先洩後蓄
    當根 K 棒：RSI 由下向上穿越 RSI_TRIGGER_LONG（動能回歸）
    當根 K 棒：收紅（close > open）且收在 EMA_20 之上（重新站回支撐）
    RSI < RSI_MAX_LONG         （避免在過熱區追高）

止損 / 止盈（結構 + 風報比）
────────────────────────────
SL = 近 SL_SWING_LOOKBACK 根的擺動低點 − ATR × SL_ATR_BUFFER
     並以 [SL_MIN_ATR, SL_MAX_ATR] × ATR 夾住止損距離（控制單筆風險）
TP = entry + (entry − SL) × RR_RATIO

新增欄位
────────
signal           1 = LONG, -1 = SHORT, 0 = no signal
signal_strength  進場條件強度（供顯示）
sl_price         該訊號的結構止損價（NaN 表示無）
tp_price         該訊號的止盈價（依風報比計算）
"""

import numpy as np
import pandas as pd

import config
from config import EMA_SHORT, EMA_LONG, EMA_TREND

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
    htf_trend: pd.Series | None = None,
) -> pd.DataFrame:
    """
    Generate trend-pullback signals plus per-trade structural SL / TP prices.

    Parameters
    ----------
    df        : DataFrame produced by the full indicator pipeline.
    htf_trend : Optional higher-timeframe EMA_200 trend (True = bullish).
                When provided it adds a confluence filter: longs require an
                up HTF trend, shorts a down HTF trend.  Pass None to skip.
    """
    df = df.copy()

    ema_s = df[f"EMA_{EMA_SHORT}"]
    ema_l = df[f"EMA_{EMA_LONG}"]
    ema_t = df[f"EMA_{EMA_TREND}"]
    rsi   = df["RSI"]
    atr   = _calc_atr(df)

    pb_look = config.PULLBACK_LOOKBACK

    # ── Layer 1: established-trend filter ─────────────────────────────────────
    trend_long  = (df["close"] > ema_t) & (ema_l > ema_t) & (ema_s > ema_l)
    trend_short = (df["close"] < ema_t) & (ema_l < ema_t) & (ema_s < ema_l)

    # Optional higher-TF confluence
    if htf_trend is not None:
        combined_idx = htf_trend.index.union(df.index)
        htf_aligned  = htf_trend.reindex(combined_idx).ffill().reindex(df.index)
        htf_up   = htf_aligned.fillna(False).astype(bool)
        htf_down = (~htf_aligned.fillna(True)).astype(bool)
        trend_long  = trend_long  & htf_up
        trend_short = trend_short & htf_down

    # ── Layer 2: pullback + momentum-return trigger ───────────────────────────
    # Pullback evidence: recently tagged EMA_20 (dip to dynamic support/resistance)
    touched_ema_long  = _rolling_any(df["low"]  <= ema_s, pb_look)
    touched_ema_short = _rolling_any(df["high"] >= ema_s, pb_look)

    # Momentum first bled off (RSI dipped / popped) within the same window
    rsi_reset_long  = _rolling_any(rsi < config.RSI_PULLBACK_LONG,  pb_look)
    rsi_reset_short = _rolling_any(rsi > config.RSI_PULLBACK_SHORT, pb_look)

    # Trigger bar: RSI crosses the trigger level in the trade direction
    rsi_cross_up = (rsi > config.RSI_TRIGGER_LONG) & (rsi.shift(1) <= config.RSI_TRIGGER_LONG)
    rsi_cross_dn = (rsi < config.RSI_TRIGGER_SHORT) & (rsi.shift(1) >= config.RSI_TRIGGER_SHORT)

    # Reclaim candle: closes back on the correct side of EMA_20 with body confirmation
    bull_candle = df["close"] > df["open"]
    bear_candle = df["close"] < df["open"]
    reclaim_long  = bull_candle & (df["close"] > ema_s)
    reclaim_short = bear_candle & (df["close"] < ema_s)

    # Not over-extended
    not_hot_long  = rsi < config.RSI_MAX_LONG
    not_hot_short = rsi > config.RSI_MIN_SHORT

    long_mask = (
        trend_long & touched_ema_long & rsi_reset_long
        & rsi_cross_up & reclaim_long & not_hot_long
    )
    short_mask = (
        trend_short & touched_ema_short & rsi_reset_short
        & rsi_cross_dn & reclaim_short & not_hot_short
    )

    # ── Structural SL / TP ────────────────────────────────────────────────────
    swing_low  = df["low"].rolling(config.SL_SWING_LOOKBACK,  min_periods=1).min()
    swing_high = df["high"].rolling(config.SL_SWING_LOOKBACK, min_periods=1).max()

    entry = df["close"]

    # Long SL: below recent swing low, with ATR buffer, distance clamped
    raw_sl_long = swing_low - atr * config.SL_ATR_BUFFER
    dist_long   = (entry - raw_sl_long).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_long = entry - dist_long
    tp_long = entry + dist_long * config.RR_RATIO

    # Short SL: above recent swing high, mirrored
    raw_sl_short = swing_high + atr * config.SL_ATR_BUFFER
    dist_short   = (raw_sl_short - entry).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_short = entry + dist_short
    tp_short = entry - dist_short * config.RR_RATIO

    # ── Assemble output ───────────────────────────────────────────────────────
    df["signal"]          = 0
    df["signal_strength"] = 0
    df["sl_price"]        = np.nan
    df["tp_price"]        = np.nan

    df.loc[long_mask,  "signal"]   = 1
    df.loc[short_mask, "signal"]   = -1
    df.loc[long_mask,  "sl_price"] = sl_long[long_mask]
    df.loc[long_mask,  "tp_price"] = tp_long[long_mask]
    df.loc[short_mask, "sl_price"] = sl_short[short_mask]
    df.loc[short_mask, "tp_price"] = tp_short[short_mask]

    # Signal strength: a simple confluence score for display (0–5)
    strength = (
        trend_long.astype(int) + trend_short.astype(int)
        + touched_ema_long.astype(int) + touched_ema_short.astype(int)
        + rsi_reset_long.astype(int) + rsi_reset_short.astype(int)
        + reclaim_long.astype(int) + reclaim_short.astype(int)
    ).clip(upper=5)
    sig_mask = long_mask | short_mask
    df.loc[sig_mask, "signal_strength"] = strength[sig_mask]

    # Safety: drop signals whose SL ended up on the wrong side of entry
    bad = (df["signal"] != 0) & (
        ((df["signal"] == 1)  & (df["sl_price"] >= entry))
        | ((df["signal"] == -1) & (df["sl_price"] <= entry))
    )
    df.loc[bad, ["signal", "signal_strength"]] = 0
    df.loc[bad, ["sl_price", "tp_price"]]      = np.nan

    return df
