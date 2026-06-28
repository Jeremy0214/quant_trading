"""
modules/technical_analyzer.py
技術面評分模組（滿分 50 分）
  - 均線趨勢  Moving Averages   20 分
  - 動能指標  MACD & RSI        15 分
  - 量價關係  Volume             15 分（含倒扣 -10）
"""

from __future__ import annotations

from typing import Tuple

import numpy as np
import pandas as pd

import config
from modules.data_fetcher import StockDataFetcher

ScoreDetail = Tuple[int, int, str]  # (score, max_score, detail_text)


class TechnicalAnalyzer:
    """計算技術指標並評分。"""

    def __init__(self, fetcher: StockDataFetcher) -> None:
        self.fetcher = fetcher
        hist = fetcher.price_history.copy()
        # Forward-fill then drop any leading NaN to avoid rolling NaN artefacts
        self.close:  pd.Series = hist["Close"].ffill().dropna()
        self.high:   pd.Series = hist["High"].ffill().dropna()
        self.low:    pd.Series = hist["Low"].ffill().dropna()
        self.volume: pd.Series = hist["Volume"].fillna(0)

    # ── 公開介面 ─────────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """
        回傳格式：
          {
            'total': int,
            'max':   50,
            'breakdown': {
              'ma':       (score, max, detail),
              'momentum': (score, max, detail),
              'volume':   (score, max, detail),
            }
          }
        """
        ma       = self._score_moving_averages()
        momentum = self._score_momentum()
        volume   = self._score_volume_price()

        # 允許量價倒扣，但合計下限為 0
        total = max(0, ma[0] + momentum[0] + volume[0])

        return {
            "total": total,
            "max": 50,
            "breakdown": {
                "ma":       ma,
                "momentum": momentum,
                "volume":   volume,
            },
        }

    # ── 私有：均線趨勢 ────────────────────────────────────────────────────────

    def _score_moving_averages(self) -> ScoreDetail:
        """
        均線趨勢（滿分 20 分）
          +20：多頭排列 (Price > MA5 > MA20 > MA60)，且均線皆向上
          +15：多頭排列，但部分均線偏平
          +10：站上月線(MA20)，MA60 向上
          + 5：站上月線，MA60 偏弱或向下（另 PRD 原文 +10，此處依 PRD 取 10）
            0：跌破月線與季線
        """
        if len(self.close) < config.MA_LONG + 5:
            return 0, config.MAX_MA_SCORE, "歷史資料不足，無法計算均線"

        ma5  = self.close.rolling(config.MA_SHORT).mean()
        ma20 = self.close.rolling(config.MA_MEDIUM).mean()
        ma60 = self.close.rolling(config.MA_LONG).mean()

        price   = self.close.iloc[-1]
        c_ma5   = ma5.iloc[-1]
        c_ma20  = ma20.iloc[-1]
        c_ma60  = ma60.iloc[-1]

        # 均線方向（與 5 個交易日前比較）
        ma5_up  = ma5.iloc[-1]  > ma5.iloc[-6]
        ma20_up = ma20.iloc[-1] > ma20.iloc[-6]
        ma60_up = ma60.iloc[-1] > ma60.iloc[-6]

        bull_align = price > c_ma5 > c_ma20 > c_ma60
        all_up     = ma5_up and ma20_up and ma60_up

        if bull_align and all_up:
            return (
                20, config.MAX_MA_SCORE,
                f"多頭排列且均線全數向上 — 股價 {price:.1f} > MA5 {c_ma5:.1f} > MA20 {c_ma20:.1f} > MA60 {c_ma60:.1f}",
            )
        if bull_align:
            return (
                15, config.MAX_MA_SCORE,
                f"多頭排列，但部分均線偏平 — 股價 {price:.1f} 站上三均線",
            )
        if price > c_ma20:
            detail = (
                f"站上月線 (MA20 {c_ma20:.1f})，MA60 {'向上' if ma60_up else '向下'}"
                f" — 中線{'偏多' if ma60_up else '偏弱'}"
            )
            return 10, config.MAX_MA_SCORE, detail

        return (
            0, config.MAX_MA_SCORE,
            f"跌破月線 ({c_ma20:.1f}) 與季線 ({c_ma60:.1f}) — 空頭走勢",
        )

    # ── 私有：動能指標 ────────────────────────────────────────────────────────

    def _score_momentum(self) -> ScoreDetail:
        """
        MACD & RSI（滿分 15 分）
          +15：RSI 40~70 且 (MACD 柱狀圖轉正 or 黃金交叉)
           +8：RSI 40~70 但 MACD 動能偏弱
           +8：RSI 70~80 偏強但注意追高
           +5：RSI < 40 偏弱 / 超賣
            0：RSI > 80 超買，或 MACD 死亡交叉
        """
        if len(self.close) < config.MACD_SLOW + config.MACD_SIGNAL + 5:
            return 0, config.MAX_MOMENTUM_SCORE, "歷史資料不足，無法計算動能指標"

        rsi  = self._calc_rsi()
        macd_line, signal_line, histogram = self._calc_macd()

        cur_rsi  = rsi.iloc[-1]
        cur_hist = histogram.iloc[-1]
        pre_hist = histogram.iloc[-2]
        cur_macd = macd_line.iloc[-1]
        pre_macd = macd_line.iloc[-2]
        cur_sig  = signal_line.iloc[-1]
        pre_sig  = signal_line.iloc[-2]

        golden_cross = cur_macd > cur_sig and pre_macd <= pre_sig
        death_cross  = cur_macd < cur_sig and pre_macd >= pre_sig
        hist_turning_positive = cur_hist > 0 and pre_hist <= 0
        macd_positive = cur_hist > 0

        # 超買或死亡交叉 → 0 分
        if cur_rsi > config.RSI_OVERBOUGHT:
            return (
                0, config.MAX_MOMENTUM_SCORE,
                f"RSI {cur_rsi:.1f} 超買過熱，短期拉回風險大",
            )
        if death_cross:
            return (
                0, config.MAX_MOMENTUM_SCORE,
                f"MACD 死亡交叉，RSI {cur_rsi:.1f} — 空頭動能增強",
            )

        # RSI 40~70
        if config.RSI_LOWER <= cur_rsi <= config.RSI_UPPER:
            if golden_cross:
                return (
                    15, config.MAX_MOMENTUM_SCORE,
                    f"RSI {cur_rsi:.1f} 健康區間，MACD 黃金交叉 — 買入訊號明確",
                )
            if hist_turning_positive:
                return (
                    15, config.MAX_MOMENTUM_SCORE,
                    f"RSI {cur_rsi:.1f} 健康區間，MACD 柱狀圖轉正 — 動能翻揚",
                )
            if macd_positive:
                return (
                    15, config.MAX_MOMENTUM_SCORE,
                    f"RSI {cur_rsi:.1f} 健康區間，MACD 柱狀圖正值 — 多頭動能",
                )
            return (
                8, config.MAX_MOMENTUM_SCORE,
                f"RSI {cur_rsi:.1f} 健康區間，但 MACD 柱狀圖仍為負值 — 動能待轉強",
            )

        # RSI 70~80
        if config.RSI_UPPER < cur_rsi <= config.RSI_OVERBOUGHT:
            return (
                8, config.MAX_MOMENTUM_SCORE,
                f"RSI {cur_rsi:.1f} 偏強，注意短線追高風險",
            )

        # RSI < 40
        if cur_rsi < config.RSI_LOWER:
            return (
                5, config.MAX_MOMENTUM_SCORE,
                f"RSI {cur_rsi:.1f} 偏弱{'，接近超賣區' if cur_rsi < config.RSI_OVERSOLD + 10 else ''}，動能不足",
            )

        return 0, config.MAX_MOMENTUM_SCORE, f"RSI {cur_rsi:.1f} 狀態異常，無法判斷"

    # ── 私有：量價關係 ────────────────────────────────────────────────────────

    def _score_volume_price(self) -> ScoreDetail:
        """
        量價關係（滿分 15 分，可倒扣 -10）
          +15：近 5 日「價漲量增」且突破近 20 日高點
          +10：近 5 日「價漲量增」
          + 5：量能平穩
          - 10：近 5 日「價跌量增」（倒貨訊號）
        """
        if len(self.close) < 25:
            return 0, config.MAX_VOLUME_SCORE, "歷史資料不足"

        close_5   = self.close.iloc[-5:]
        vol_5     = self.volume.iloc[-5:]
        avg_vol_20 = self.volume.iloc[-20:].mean()
        high_20   = self.high.iloc[-20:].max()

        price_chg     = close_5.iloc[-1] - close_5.iloc[0]
        price_up      = price_chg > 0
        price_down    = price_chg < 0
        avg_vol_5     = vol_5.mean()
        vol_increase  = avg_vol_5 > avg_vol_20 * config.VOLUME_INCREASE_RATIO
        vol_stable    = avg_vol_20 * 0.8 <= avg_vol_5 <= avg_vol_20 * config.VOLUME_INCREASE_RATIO

        # 近期收盤是否突破（或貼近）近 20 日最高點
        breakout = self.close.iloc[-1] >= high_20 * 0.99

        if price_down and vol_increase:
            return (
                -10, config.MAX_VOLUME_SCORE,
                f"量增價跌 — 疑似主力倒貨，⚠️ 風險警示",
            )
        if price_up and vol_increase and breakout:
            return (
                15, config.MAX_VOLUME_SCORE,
                f"量增價漲並突破近 20 日高點 ({high_20:.1f}) — 強勁突破訊號",
            )
        if price_up and vol_increase:
            return (
                10, config.MAX_VOLUME_SCORE,
                "量增價漲 — 資金動能充足",
            )
        if vol_stable:
            return (
                5, config.MAX_VOLUME_SCORE,
                "量能平穩 — 正常整理",
            )
        if price_up:
            return (
                5, config.MAX_VOLUME_SCORE,
                "價格上漲但量能偏弱，需觀察後續量能是否跟上",
            )

        return 3, config.MAX_VOLUME_SCORE, "量能偏弱，觀望為宜"

    # ── 指標計算 ──────────────────────────────────────────────────────────────

    def _calc_rsi(self, period: int = config.RSI_PERIOD) -> pd.Series:
        delta = self.close.diff()
        gain  = delta.clip(lower=0)
        loss  = (-delta).clip(lower=0)
        avg_gain = gain.ewm(com=period - 1, min_periods=period).mean()
        avg_loss = loss.ewm(com=period - 1, min_periods=period).mean()
        rs  = avg_gain / avg_loss.replace(0, np.nan)
        rsi = 100 - (100 / (1 + rs))
        return rsi.fillna(50)

    def _calc_macd(
        self,
        fast: int   = config.MACD_FAST,
        slow: int   = config.MACD_SLOW,
        signal: int = config.MACD_SIGNAL,
    ) -> tuple[pd.Series, pd.Series, pd.Series]:
        ema_fast    = self.close.ewm(span=fast,   min_periods=fast).mean()
        ema_slow    = self.close.ewm(span=slow,   min_periods=slow).mean()
        macd_line   = ema_fast - ema_slow
        signal_line = macd_line.ewm(span=signal,  min_periods=signal).mean()
        histogram   = macd_line - signal_line
        return macd_line, signal_line, histogram
