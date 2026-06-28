"""
modules/price_target.py
根據基本面與技術面綜合分析，估算目標價格區間與停損參考。

計算邏輯：
  1. 評分轉換漲跌幅 — 依總分劃分五個區間，對應預期報酬率範圍
  2. P/E 估算目標價 — EPS × 合理 P/E（依得分給予估值溢/折價）
  3. 技術壓力參考   — 近 20/60 日最高點與 52 週高點
  4. 停損建議       — 僅在看多情境下提供
"""

from __future__ import annotations

from typing import Optional

from modules.data_fetcher import StockDataFetcher


# ── 評分 → 預期報酬率對照表 ─────────────────────────────────────────────────
# (最低分, 最高分): (漲跌幅下界, 漲跌幅上界, 策略標籤, P/E倍數調整係數)
_SCORE_BANDS = [
    (80, 100,  0.15,  0.25,  "積極做多",  1.15),
    (60,  79,  0.08,  0.15,  "偏多操作",  1.05),
    (40,  59, -0.03,  0.05,  "中性觀望",  0.95),
    (20,  39, -0.12, -0.03,  "偏空減碼",  0.85),
    ( 0,  19, -0.25, -0.12,  "強烈規避",  0.75),
]


class PriceTargetCalculator:
    """計算目標價格區間與相關技術壓力位。"""

    def __init__(
        self,
        fetcher: StockDataFetcher,
        fund_result: dict,
        tech_result: dict,
    ) -> None:
        self.fetcher = fetcher
        self.fund    = fund_result
        self.tech    = tech_result

    def calculate(self) -> dict:
        hist          = self.fetcher.price_history
        close         = hist["Close"].ffill().dropna()
        high_series   = hist["High"].ffill().dropna()
        # 優先使用 data_fetcher 中已取得的即時 / 最新股價
        current_price = (
            self.fetcher.current_price
            if self.fetcher.current_price and self.fetcher.current_price > 0
            else float(close.iloc[-1])
        )

        fund_score  = self.fund["total"]
        tech_score  = self.tech["total"]
        total_score = max(0, min(100, fund_score + tech_score))

        # ── 1. 評分轉換 ──────────────────────────────────────────────────────
        u_low = u_high = 0.0
        strategy    = ""
        pe_adj      = 1.0
        for lo, hi, ul, uh, strat, pa in _SCORE_BANDS:
            if lo <= total_score <= hi:
                u_low, u_high = ul, uh
                strategy      = strat
                pe_adj        = pa
                break

        target_low  = current_price * (1 + u_low)
        target_high = current_price * (1 + u_high)

        # ── 2. P/E 估算目標價 ────────────────────────────────────────────────
        info       = self.fetcher.stock_info
        eps:  Optional[float] = info.get("trailingEps")
        c_pe: Optional[float] = info.get("trailingPE")

        pe_target: Optional[float] = None
        fair_pe:   Optional[float] = None

        if eps and eps > 0 and c_pe and 0 < c_pe < 500:
            fair_pe   = round(c_pe * pe_adj, 1)
            pe_target = eps * fair_pe

        # ── 3. 技術壓力位 ────────────────────────────────────────────────────
        n = len(high_series)
        high_20  = float(high_series.tail(20).max())
        high_60  = float(high_series.tail(60).max())
        high_252 = float(high_series.tail(min(252, n)).max())

        # ── 4. 停損建議 ──────────────────────────────────────────────────────
        stop_loss: Optional[float] = None
        stop_pct:  Optional[float] = None
        if total_score >= 60:
            stop_pct  = -0.07
            stop_loss = current_price * (1 + stop_pct)
        elif total_score >= 40:
            stop_pct  = -0.10
            stop_loss = current_price * (1 + stop_pct)

        return {
            "current_price":   current_price,
            "total_score":     total_score,
            "strategy":        strategy,
            "target_low":      target_low,
            "target_high":     target_high,
            "upside_low_pct":  u_low  * 100,
            "upside_high_pct": u_high * 100,
            "pe_target":       pe_target,
            "fair_pe":         fair_pe,
            "current_pe":      c_pe,
            "eps":             eps,
            "high_20":         high_20,
            "high_60":         high_60,
            "high_252":        high_252,
            "stop_loss":       stop_loss,
            "stop_pct":        stop_pct,
        }
