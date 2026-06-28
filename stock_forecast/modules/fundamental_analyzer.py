"""
modules/fundamental_analyzer.py
基本面評分模組（滿分 50 分）
  - 營收成長性  15 分
  - EPS 獲利能力 15 分
  - P/E 估值     10 分
  - ROE 經營效率 10 分
"""

from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd

import config
from modules.data_fetcher import StockDataFetcher

ScoreDetail = Tuple[int, int, str]   # (score, max_score, detail_text)


class FundamentalAnalyzer:
    """計算並彙整基本面各項得分。"""

    def __init__(self, fetcher: StockDataFetcher) -> None:
        self.fetcher = fetcher

    # ── 公開介面 ─────────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """
        執行全部基本面評分，回傳結構化結果。
        回傳格式：
          {
            'total': int,
            'max':   50,
            'breakdown': {
              'revenue':  (score, max, detail),
              'eps':      (score, max, detail),
              'pe':       (score, max, detail),
              'roe':      (score, max, detail),
            }
          }
        """
        revenue = self._score_revenue()
        eps     = self._score_eps()
        pe      = self._score_pe()
        roe     = self._score_roe()

        total = revenue[0] + eps[0] + pe[0] + roe[0]

        return {
            "total": total,
            "max": 50,
            "breakdown": {
                "revenue": revenue,
                "eps":     eps,
                "pe":      pe,
                "roe":     roe,
            },
        }

    # ── 私有：各模組評分 ──────────────────────────────────────────────────────

    def _score_revenue(self) -> ScoreDetail:
        """
        月營收 YoY 成長性（滿分 15 分）
          +15：單月 YoY > 10% 且 累計 YoY > 10%
          + 5：單月 YoY > 0%
            0：YoY 衰退
        """
        rev = self.fetcher.monthly_revenue
        if rev is None:
            return 0, config.MAX_REVENUE_SCORE, "月營收資料無法取得（MOPS 查詢失敗），跳過評分"

        monthly_yoy: Optional[float] = rev.get("monthly_yoy")
        ytd_yoy:     Optional[float] = rev.get("ytd_yoy")

        if monthly_yoy is None:
            return 0, config.MAX_REVENUE_SCORE, "月營收 YoY 資料不足，跳過評分"

        if monthly_yoy > config.REVENUE_YOY_HIGH:
            ytd_part = (
                f"，累計 YoY +{ytd_yoy:.1f}%"
                if ytd_yoy is not None and ytd_yoy > config.REVENUE_YOY_HIGH
                else ""
            )
            if ytd_yoy is not None and ytd_yoy > config.REVENUE_YOY_HIGH:
                return (
                    15, config.MAX_REVENUE_SCORE,
                    f"月營收 YoY +{monthly_yoy:.1f}%{ytd_part} — 雙位數成長，動能強勁",
                )
            else:
                ytd_note = f"，累計 YoY {ytd_yoy:.1f}%" if ytd_yoy is not None else ""
                return (
                    5, config.MAX_REVENUE_SCORE,
                    f"月營收 YoY +{monthly_yoy:.1f}%{ytd_note} — 單月強，但累計未達雙位數",
                )

        if monthly_yoy > 0:
            return (
                5, config.MAX_REVENUE_SCORE,
                f"月營收 YoY +{monthly_yoy:.1f}% — 小幅成長",
            )

        return (
            0, config.MAX_REVENUE_SCORE,
            f"月營收 YoY {monthly_yoy:.1f}% — 年衰退，成長動能不足",
        )

    def _score_eps(self) -> ScoreDetail:
        """
        EPS 獲利能力（滿分 15 分）
          +15：TTM EPS 年增 or 歷史新高
          +10：EPS 正值且穩定
            0：EPS 負值
        """
        info = self.fetcher.stock_info
        trailing_eps: Optional[float] = info.get("trailingEps")
        eps_growth:   Optional[float] = info.get("earningsGrowth")   # decimal

        # 嘗試從 yfinance info 取得
        if trailing_eps is None:
            return self._score_eps_from_statements()

        if trailing_eps < 0:
            return (
                0, config.MAX_EPS_SCORE,
                f"EPS {trailing_eps:.2f} 元 — 虧損，獲利能力不佳",
            )

        if eps_growth is not None and eps_growth > 0:
            return (
                15, config.MAX_EPS_SCORE,
                f"EPS {trailing_eps:.2f} 元，年增 {eps_growth * 100:.1f}% — 持續成長，獲利動能強",
            )

        # EPS 正值但無成長資訊或持平
        return (
            10, config.MAX_EPS_SCORE,
            f"EPS {trailing_eps:.2f} 元 — 正值穩定，但成長性待確認",
        )

    def _score_eps_from_statements(self) -> ScoreDetail:
        """備援：從季報財務表計算近四季 EPS。"""
        try:
            qincome = self.fetcher.yf_ticker.quarterly_income_stmt
            if qincome is None or qincome.empty:
                return 0, config.MAX_EPS_SCORE, "EPS 資料無法取得，跳過評分"

            eps_keys = ["Basic EPS", "Diluted EPS", "Basic Earnings Per Share"]
            for key in eps_keys:
                if key in qincome.index:
                    recent = qincome.loc[key].head(4)
                    ttm = recent.sum()
                    if pd.isna(ttm):
                        continue
                    if ttm < 0:
                        return 0, config.MAX_EPS_SCORE, f"近四季 EPS 合計 {ttm:.2f} — 虧損"
                    # 判斷是否年增
                    if len(recent) >= 4:
                        prev_4 = qincome.loc[key].iloc[4:8]
                        prev_ttm = prev_4.sum() if len(prev_4) == 4 else None
                        if prev_ttm is not None and not pd.isna(prev_ttm) and prev_ttm != 0:
                            growth = (ttm - prev_ttm) / abs(prev_ttm)
                            if growth > 0:
                                return (
                                    15, config.MAX_EPS_SCORE,
                                    f"近四季 EPS {ttm:.2f} 元，年增 {growth*100:.1f}% — 成長趨勢",
                                )
                    return (
                        10, config.MAX_EPS_SCORE,
                        f"近四季 EPS {ttm:.2f} 元 — 正值穩定",
                    )
        except Exception:
            pass
        return 0, config.MAX_EPS_SCORE, "EPS 資料無法取得，跳過評分"

    def _score_pe(self) -> ScoreDetail:
        """
        本益比估值（滿分 10 分）
          +10：P/E < 15
          + 5：P/E 15~20
          + 3：P/E 20~25（偏高但可接受）
            0：P/E > 25
        """
        info = self.fetcher.stock_info
        pe: Optional[float] = info.get("trailingPE") or info.get("forwardPE")

        if pe is None or pe <= 0 or pe > 2000:
            return 0, config.MAX_PE_SCORE, "P/E 資料無法取得或不合理，跳過評分"

        if pe < config.PE_LOW_THRESHOLD:
            return (
                10, config.MAX_PE_SCORE,
                f"P/E {pe:.1f}x — 低估值，安全邊際充足",
            )
        if pe <= config.PE_MED_THRESHOLD:
            return (
                5, config.MAX_PE_SCORE,
                f"P/E {pe:.1f}x — 合理估值區間",
            )
        if pe <= config.PE_HIGH_THRESHOLD:
            return (
                3, config.MAX_PE_SCORE,
                f"P/E {pe:.1f}x — 略高，留意估值風險",
            )
        return (
            0, config.MAX_PE_SCORE,
            f"P/E {pe:.1f}x — 估值過高，追價風險大",
        )

    def _score_roe(self) -> ScoreDetail:
        """
        股東權益報酬率（滿分 10 分）
          +10：ROE > 15%
          + 5：ROE 10%~15%
            0：ROE < 10%
        """
        info = self.fetcher.stock_info
        roe_raw: Optional[float] = info.get("returnOnEquity")

        if roe_raw is None:
            return self._score_roe_from_statements()

        roe = roe_raw * 100  # 轉為百分比

        if roe > config.ROE_HIGH_THRESHOLD:
            return (
                10, config.MAX_ROE_SCORE,
                f"ROE {roe:.1f}% — 高效益，具護城河特徵",
            )
        if roe >= config.ROE_MED_THRESHOLD:
            return (
                5, config.MAX_ROE_SCORE,
                f"ROE {roe:.1f}% — 合格水準",
            )
        return (
            0, config.MAX_ROE_SCORE,
            f"ROE {roe:.1f}% — 資本運用效率偏低",
        )

    def _score_roe_from_statements(self) -> ScoreDetail:
        """備援：從年報計算 ROE。"""
        try:
            income = self.fetcher.yf_ticker.income_stmt
            bs     = self.fetcher.yf_ticker.balance_sheet

            if income is None or bs is None or income.empty or bs.empty:
                return 0, config.MAX_ROE_SCORE, "ROE 資料無法取得，跳過評分"

            ni = None
            for key in ["Net Income", "Net Income Common Stockholders"]:
                if key in income.index:
                    ni = income.loc[key].iloc[0]
                    break

            eq = None
            for key in [
                "Stockholders Equity",
                "Total Stockholders Equity",
                "Common Stock Equity",
            ]:
                if key in bs.index:
                    eq = bs.loc[key].iloc[0]
                    break

            if ni is not None and eq is not None and eq != 0:
                roe = (ni / eq) * 100
                if roe > config.ROE_HIGH_THRESHOLD:
                    return 10, config.MAX_ROE_SCORE, f"ROE {roe:.1f}% — 高效益"
                if roe >= config.ROE_MED_THRESHOLD:
                    return 5, config.MAX_ROE_SCORE, f"ROE {roe:.1f}% — 合格水準"
                return 0, config.MAX_ROE_SCORE, f"ROE {roe:.1f}% — 效益偏低"
        except Exception:
            pass
        return 0, config.MAX_ROE_SCORE, "ROE 資料無法取得，跳過評分"
