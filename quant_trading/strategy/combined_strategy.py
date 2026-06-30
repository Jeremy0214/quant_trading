"""
strategy/combined_strategy.py
Strategy v4.0 ??Quality Trend-Pullback with Structural SL/TP
=============================================================

閮剛??格?
????????
1. ????嚗 v3 ??撅日脣?嗆?嚗隅?Ｔ??矽???賢?甇賂??箇?銝?
   ?銝?憿??蕪嚗蝙瘥??脣?賢???釭雿蔭??
     (a) EMA 200 ???蕪 ??蝣箄?憭扯隅?Ｙ?甇???孵?嚗?瞈曄?游?閮???
     (b) ?蝣箄?         ??閫貊 K 璉?鈭日????潸???????祕??
     (c) ?漲撱嗡撓?蕪     ??頝?EMA 20 ??銝蕭嚗?眺?函?扔蝡胯?
2. ?瘥?嚗璅◢?望?????1.7嚗onfig.RR_RATIO嚗?
   撖行葫 avgWin/avgLoss ??1.6嚗帘摰???1.5 閬???
3. ?芸?憭?LONG_ONLY = True嚗?BTC/ETH ?瑟???嚗??桀???
   蝝?58??0%嚗＊???潛征??45%嚗??征?桐誑?憭批?蝯?????
4. 甇Ｘ?????餈??箏?雿? ??ATR 蝺抵?嚗◤?誨銵函?瑽?甇?憯?
5. 甇Ｙ?????entry + risk ? RR_RATIO嚗?蝑???蝞?

?脣?摩嚗??殷???LONG_ONLY=False嚗征?桃?∪?嚗?
??????????????????????????????????????????????????
蝚砌?撅?頞典?蕪
    close > EMA_200            嚗?銝?隅?Ｙ?嚗?
    EMA_50 > EMA_200           嚗葉?隅?Ｗ?銝?
    EMA_20 > EMA_50            嚗???賢?銝?
    EMA_200 ????           嚗隅?Ｗ??改???湛?

蝚砌?撅??矽 + ??飛
    餈?PULLBACK_LOOKBACK ?孵?曉?頦?EMA_20嚗ow ??EMA_20嚗?
    餈?PULLBACK_LOOKBACK ?孵 RSI ?曇???RSI_PULLBACK_LONG
    ?嗆嚗SI ?曹???蝛輯? RSI_TRIGGER_LONG嚗??賢?甇賂?
    ?嗆嚗蝝??嗥蝡? EMA_20 銋?嚗??嗅 K 璉????挾

蝚砌?撅??釭?蕪嚗4 ?啣?嚗?
    ?漱??> 餈?VOL_MA_PERIOD ?孵???? VOL_MULT
    RSI < RSI_MAX_LONG嚗??嚗?
    close ??EMA_20 < ATR ? EXT_MAX_ATR嚗?漲撱嗡撓嚗?

甇Ｘ? / 甇Ｙ?嚗?瑽?+ 憸典瘥?
????????????????????????????
SL = 餈?SL_SWING_LOOKBACK ?寧??箏?雿? ??ATR ? SL_ATR_BUFFER
     頝憭暹 [SL_MIN_ATR, SL_MAX_ATR] ? ATR
TP = entry + (entry ??SL) ? RR_RATIO

頛詨甈?
????????
signal           1 = LONG, -1 = SHORT, 0 = no signal
signal_strength  ?脣璇辣撘瑕漲嚗???嚗? Discord 憿舐內嚗?
sl_price         閰脰???蝯?甇Ｘ???
tp_price         閰脰???甇Ｙ???
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
    Generate quality trend-pullback signals plus per-trade structural SL/TP.

    Parameters
    ----------
    df        : DataFrame produced by the full indicator pipeline.
    htf_trend : Optional higher-timeframe EMA_200 trend (True = bullish).
    """
    df = df.copy()

    close = df["close"]; openp = df["open"]
    high  = df["high"];  low   = df["low"]
    ema_s = df[f"EMA_{EMA_SHORT}"]
    ema_l = df[f"EMA_{EMA_LONG}"]
    ema_t = df[f"EMA_{EMA_TREND}"]
    rsi   = df["RSI"]
    atr   = _calc_atr(df)
    vol_ma = df["volume"].rolling(config.VOL_MA_PERIOD, min_periods=1).mean()

    pb_look = config.PULLBACK_LOOKBACK

    # ?? Layer 1: established trend + slope filter ?????????????????????????????
    slope_up = ema_t > ema_t.shift(config.EMA_SLOPE_LOOKBACK)
    slope_dn = ema_t < ema_t.shift(config.EMA_SLOPE_LOOKBACK)
    trend_long  = (close > ema_t) & (ema_l > ema_t) & (ema_s > ema_l) & slope_up
    trend_short = (close < ema_t) & (ema_l < ema_t) & (ema_s < ema_l) & slope_dn

    # Optional HTF confluence
    if htf_trend is not None:
        combined_idx = htf_trend.index.union(df.index)
        htf_aligned  = htf_trend.reindex(combined_idx).ffill().reindex(df.index)
        htf_up   = htf_aligned.fillna(False).astype(bool)
        htf_down = (~htf_aligned.fillna(True)).astype(bool)
        trend_long  = trend_long  & htf_up
        trend_short = trend_short & htf_down

    # ?? Layer 2: pullback + momentum-return trigger ???????????????????????????
    touched_ema_long  = _rolling_any(low  <= ema_s, pb_look)
    touched_ema_short = _rolling_any(high >= ema_s, pb_look)

    rsi_reset_long  = _rolling_any(rsi < config.RSI_PULLBACK_LONG,  pb_look)
    rsi_reset_short = _rolling_any(rsi > config.RSI_PULLBACK_SHORT, pb_look)

    rsi_cross_up = (rsi > config.RSI_TRIGGER_LONG)  & (rsi.shift(1) <= config.RSI_TRIGGER_LONG)
    rsi_cross_dn = (rsi < config.RSI_TRIGGER_SHORT) & (rsi.shift(1) >= config.RSI_TRIGGER_SHORT)

    # Confirmation candle: close on the correct side of EMA_20,
    # with bullish/bearish body and closes in the favourable half of the range
    rng  = (high - low).replace(0, np.nan)
    cpos = (close - low) / rng
    reclaim_long  = (close > openp) & (close > ema_s) & (cpos > 0.5)
    reclaim_short = (close < openp) & (close < ema_s) & (cpos < 0.5)

    # ?? Layer 3: quality filters (v4) ????????????????????????????????????????
    vol_ok        = df["volume"] > vol_ma * config.VOL_MULT
    not_hot_long  = rsi < config.RSI_MAX_LONG
    not_hot_short = rsi > config.RSI_MIN_SHORT
    ext_ok_long   = (close - ema_s) < atr * config.EXT_MAX_ATR
    ext_ok_short  = (ema_s - close) < atr * config.EXT_MAX_ATR

    long_mask = (
        trend_long & touched_ema_long & rsi_reset_long & rsi_cross_up
        & reclaim_long & vol_ok & not_hot_long & ext_ok_long
    )
    short_mask = (
        trend_short & touched_ema_short & rsi_reset_short & rsi_cross_dn
        & reclaim_short & vol_ok & not_hot_short & ext_ok_short
    )

    if config.LONG_ONLY:
        short_mask = pd.Series(False, index=df.index)

    # ?? Structural SL / TP ????????????????????????????????????????????????????
    swing_low  = low.rolling(config.SL_SWING_LOOKBACK,  min_periods=1).min()
    swing_high = high.rolling(config.SL_SWING_LOOKBACK, min_periods=1).max()

    entry = close

    raw_sl_long = swing_low - atr * config.SL_ATR_BUFFER
    dist_long   = (entry - raw_sl_long).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_long = entry - dist_long
    tp_long = entry + dist_long * config.RR_RATIO

    raw_sl_short = swing_high + atr * config.SL_ATR_BUFFER
    dist_short   = (raw_sl_short - entry).clip(
        lower=atr * config.SL_MIN_ATR, upper=atr * config.SL_MAX_ATR
    )
    sl_short = entry + dist_short
    tp_short = entry - dist_short * config.RR_RATIO

    # ?? Assemble output ???????????????????????????????????????????????????????
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

    # Signal strength score (0??) for Discord display
    strength = (
        trend_long.astype(int) + trend_short.astype(int)
        + touched_ema_long.astype(int) + touched_ema_short.astype(int)
        + rsi_reset_long.astype(int) + rsi_reset_short.astype(int)
        + vol_ok.astype(int)
        + reclaim_long.astype(int) + reclaim_short.astype(int)
    ).clip(upper=5)
    sig_mask = long_mask | short_mask
    df.loc[sig_mask, "signal_strength"] = strength[sig_mask]

    # Safety: drop signals where SL ended up on the wrong side of entry
    bad = (df["signal"] != 0) & (
        ((df["signal"] == 1)  & (df["sl_price"] >= entry))
        | ((df["signal"] == -1) & (df["sl_price"] <= entry))
    )
    df.loc[bad, ["signal", "signal_strength"]] = 0
    df.loc[bad, ["sl_price", "tp_price"]]      = np.nan

    return df
