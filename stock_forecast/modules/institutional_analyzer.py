"""
modules/institutional_analyzer.py
三大法人動向分析（滿分 20 分，中性基線 10 分）

  外資淨買超   最高 12 分
  投信淨買超   最高  5 分
  自營商淨買超 最高  3 分

  得分 > 10 → 法人積極買進，加分
  得分 < 10 → 法人偏向賣出，減分
  綜合分數調整 = 得分 - 10，範圍 -10 ~ +10，加入總信心指數。
  資料無法取得時：得分 = 10（中性，不影響總分）。
"""

from __future__ import annotations

from typing import Optional, Tuple

import config
from modules.data_fetcher import StockDataFetcher

ScoreDetail = Tuple[int, int, str]   # (score, max_score, detail_text)


class InstitutionalAnalyzer:
    """計算三大法人買賣超得分。"""

    def __init__(self, fetcher: StockDataFetcher) -> None:
        self.fetcher = fetcher

    # ── 公開介面 ─────────────────────────────────────────────────────────────

    def analyze(self) -> dict:
        """
        回傳格式：
          {
            'total':       int,        # 0-20
            'max':         20,
            'adjustment':  int,        # total - 10，範圍 -10~+10
            'available':   bool,       # 是否成功取得資料
            'date':        str,        # 資料日期
            'source':      str,        # 資料來源
            'breakdown': {
              'foreign':  (score, max, detail, net_shares),
              'trust':    (score, max, detail, net_shares),
              'dealer':   (score, max, detail, net_shares),
            }
          }
        """
        data = self.fetcher.institutional_data

        if data is None:
            return self._unavailable_result()

        foreign_score, foreign_detail = self._score_foreign(data["foreign"])
        trust_score,   trust_detail   = self._score_trust(data["trust"])
        dealer_score,  dealer_detail  = self._score_dealer(data["dealer"])

        total = min(
            config.MAX_INSTI_SCORE,
            foreign_score + trust_score + dealer_score,
        )
        adjustment = total - 10   # -10 ~ +10

        return {
            "total":      total,
            "max":        config.MAX_INSTI_SCORE,
            "adjustment": adjustment,
            "available":  True,
            "date":       data.get("date", ""),
            "source":     data.get("source", ""),
            "breakdown": {
                "foreign": (foreign_score, config.MAX_INSTI_FOREIGN,
                            foreign_detail, data["foreign"]),
                "trust":   (trust_score,   config.MAX_INSTI_TRUST,
                            trust_detail,   data["trust"]),
                "dealer":  (dealer_score,  config.MAX_INSTI_DEALER,
                            dealer_detail,  data["dealer"]),
            },
            "total_net": data.get("total", 0),
        }

    # ── 私有：各機構評分 ──────────────────────────────────────────────────────

    def _score_foreign(self, net: int) -> tuple[int, str]:
        """外資淨買超評分（滿分 12 分）。net 單位：股。"""
        lots = net // 1000   # 轉為張

        if net >= config.INSTI_FOREIGN_HIGH:
            return 12, f"大力買超 {lots:+,} 張 — 外資強力做多"
        if net >= config.INSTI_FOREIGN_MED:
            return 9,  f"中度買超 {lots:+,} 張 — 外資偏多"
        if net > 0:
            return 6,  f"小幅買超 {lots:+,} 張 — 外資略偏多"
        if net == 0:
            return 3,  "外資中性（無明顯買賣超）"
        # 賣超
        if net >= -config.INSTI_FOREIGN_MED:
            return 1,  f"小幅賣超 {lots:+,} 張 — 外資略偏空"
        return 0, f"大幅賣超 {lots:+,} 張 — 外資偏空"

    def _score_trust(self, net: int) -> tuple[int, str]:
        """投信淨買超評分（滿分 5 分）。net 單位：股。"""
        lots = net // 1000

        if net >= config.INSTI_TRUST_HIGH:
            return 5, f"大力買超 {lots:+,} 張 — 投信強力佈局"
        if net >= config.INSTI_TRUST_MED:
            return 4, f"買超 {lots:+,} 張 — 投信積極買進"
        if net > 0:
            return 3, f"小幅買超 {lots:+,} 張 — 投信偏多"
        if net == 0:
            return 2, "投信中性"
        return 0, f"賣超 {lots:+,} 張 — 投信偏空"

    def _score_dealer(self, net: int) -> tuple[int, str]:
        """自營商淨買超評分（滿分 3 分）。net 單位：股。"""
        lots = net // 1000

        if net > 0:
            return 3, f"買超 {lots:+,} 張"
        if net == 0:
            return 1, "自營商中性"
        return 0, f"賣超 {lots:+,} 張"

    # ── 私有：資料無法取得 ────────────────────────────────────────────────────

    @staticmethod
    def _unavailable_result() -> dict:
        """無法取得法人資料時，回傳中性（不影響總分）。"""
        return {
            "total":      10,
            "max":        config.MAX_INSTI_SCORE,
            "adjustment": 0,
            "available":  False,
            "date":       "",
            "source":     "",
            "breakdown": {
                "foreign": (0, config.MAX_INSTI_FOREIGN, "資料無法取得", 0),
                "trust":   (0, config.MAX_INSTI_TRUST,   "資料無法取得", 0),
                "dealer":  (0, config.MAX_INSTI_DEALER,  "資料無法取得", 0),
            },
            "total_net": 0,
        }
