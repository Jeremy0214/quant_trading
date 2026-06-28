"""
modules/report_generator.py
負責將分析結果格式化並輸出至終端。
"""

from __future__ import annotations

from datetime import datetime
from typing import Tuple

from colorama import Fore, Style, init as colorama_init

import config
from modules.data_fetcher import StockDataFetcher

colorama_init(autoreset=True)

# ── 輔助函式 ──────────────────────────────────────────────────────────────────

W_CONST = 66   # 全域常數，供 row() 使用


def _bar(score: int, max_score: int, width: int = 10) -> str:
    """產生 ASCII 進度條，支援負分（倒扣）。"""
    if max_score <= 0:
        return "░" * width
    ratio = max(0.0, min(1.0, score / max_score))
    filled = round(ratio * width)
    return Fore.GREEN + "█" * filled + Style.DIM + "░" * (width - filled) + Style.RESET_ALL


def _pct_bar(score: int, total: int = 100, width: int = 30) -> str:
    """產生整體信心進度條。"""
    ratio = max(0.0, min(1.0, score / total))
    filled = round(ratio * width)
    if ratio >= 0.8:
        color = Fore.RED     # 強烈訊號（紅色醒目）
    elif ratio >= 0.6:
        color = Fore.YELLOW
    elif ratio >= 0.4:
        color = Fore.WHITE
    else:
        color = Fore.CYAN
    return color + "█" * filled + Style.DIM + "░" * (width - filled) + Style.RESET_ALL


def _recommendation(score: int) -> Tuple[str, str, str]:
    """依總分回傳 (建議標籤, 信心等級, 解讀說明)。"""
    if score >= 80:
        return (
            "【強烈買入  Strong Buy】",
            "🔴 高 (High)",
            "基本面強勁且技術面剛發動/處於強勢多頭，為極佳的進場點。",
        )
    if score >= 60:
        return (
            "【適合買入 / 偏多看待  Buy】",
            "🟡 中等 (Medium)",
            "體質良好且趨勢偏多，可考慮分批佈局。",
        )
    if score >= 40:
        return (
            "【觀望 / 中立  Hold】",
            "⚪ 低 (Low)",
            "可能基本面佳但技術面轉弱，或技術面轉強但缺乏基本面支撐。建議等待更明確的訊號。",
        )
    if score >= 20:
        return (
            "【建議減碼 / 偏空看待  Sell】",
            "🟡 中等 (Medium)",
            "趨勢已破壞，且基本面成長放緩，建議尋找賣點。",
        )
    return (
        "【強烈賣出 / 避開  Strong Sell】",
        "🔴 高 (High)",
        "基本面衰退且技術面空頭排列，切勿接刀。",
    )


def _rec_color(score: int) -> str:
    if score >= 80:
        return Fore.RED + Style.BRIGHT
    if score >= 60:
        return Fore.YELLOW + Style.BRIGHT
    if score >= 40:
        return Fore.WHITE
    if score >= 20:
        return Fore.CYAN
    return Fore.BLUE + Style.BRIGHT


# ── 主類別 ───────────────────────────────────────────────────────────────────

class ReportGenerator:
    """格式化並輸出完整評估報告。"""

    WIDTH = 106  # 報告內容寬度（顯示欄位數）；終端需 ≥108 欄

    def __init__(
        self,
        fetcher: StockDataFetcher,
        fund_result: dict,
        tech_result: dict,
        price_target: dict,
        insti_result: dict | None = None,
    ) -> None:
        self.fetcher       = fetcher
        self.fund          = fund_result
        self.tech          = tech_result
        self.price_target  = price_target
        self.insti         = insti_result or {
            "total": 10, "max": 20, "adjustment": 0, "available": False,
            "date": "", "source": "", "breakdown": {
                "foreign": (0, 12, "資料無法取得", 0),
                "trust":   (0,  5, "資料無法取得", 0),
                "dealer":  (0,  3, "資料無法取得", 0),
            }, "total_net": 0,
        }

    # ── 公開介面 ─────────────────────────────────────────────────────────────

    def print_report(self) -> None:
        import re
        import unicodedata

        fund_score  = self.fund["total"]
        tech_score  = self.tech["total"]
        insti_adj   = self.insti["adjustment"]   # -10 ~ +10
        total_score = max(0, min(100, fund_score + tech_score + insti_adj))

        rec_label, confidence, _ = _recommendation(total_score)
        rec_col = _rec_color(total_score)
        W = self.WIDTH

        _ansi = re.compile(r"\x1b\[[0-9;]*m")

        def _vis(s: str) -> int:
            """Display width: strips ANSI, counts CJK/emoji as 2 columns."""
            clean = _ansi.sub("", s)
            width = 0
            for ch in clean:
                eaw = unicodedata.east_asian_width(ch)
                width += 2 if eaw in ("W", "F") else 1
            return width

        def _trunc(s: str, max_w: int) -> str:
            """Truncate string so its display width ≤ max_w, appending '…' if cut."""
            clean = _ansi.sub("", s)
            w = 0
            idx = 0
            for i, ch in enumerate(clean):
                eaw = unicodedata.east_asian_width(ch)
                w += 2 if eaw in ("W", "F") else 1
                if w > max_w:
                    break
                idx = i + 1
            if idx < len(clean):
                return clean[:idx] + "…"
            return s

        def _dpad(s: str, width: int) -> str:
            """Pad string to `width` display columns (CJK-aware)."""
            return s + " " * max(0, width - _vis(s))

        def row(text: str = "") -> str:
            """Pad (or truncate) text to exactly W display chars (no borders)."""
            v = _vis(text)
            if v > W:
                text = _trunc(text, W - 1)
                v = _vis(text)
            return text + " " * max(0, W - v)

        def line(text: str = "") -> str:
            """Full border line: ║<padded text>║"""
            return (
                Fore.CYAN + "║" + Style.RESET_ALL
                + row(text)
                + Fore.CYAN + "║" + Style.RESET_ALL
            )

        def center_line(text: str) -> str:
            vis = _vis(text)
            pad = W - vis
            return (
                Fore.CYAN + "║" + Style.RESET_ALL
                + " " * (pad // 2) + text + " " * (pad - pad // 2)
                + Fore.CYAN + "║" + Style.RESET_ALL
            )

        DIV    = "─" * W
        TOP    = Fore.CYAN + "╔" + "═" * W + "╗" + Style.RESET_ALL
        BOT    = Fore.CYAN + "╚" + "═" * W + "╝" + Style.RESET_ALL
        MID    = Fore.CYAN + "╠" + "═" * W + "╣" + Style.RESET_ALL

        out = ["", TOP]

        # ── 標題 ──────────────────────────────────────────────────────────
        title = (
            "  台股評估報告  ──  "
            + Fore.YELLOW + Style.BRIGHT
            + f"{self.fetcher.company_name}  ({self.fetcher.ticker_symbol})"
            + Style.RESET_ALL
        )
        out.append(center_line(title))
        out.append(line(f"  分析日期: {datetime.now().strftime('%Y-%m-%d %H:%M')}"))

        # ── 基本面 ──────────────────────────────────────────────────────────
        out.append(MID)
        out.append(line(Fore.GREEN + Style.BRIGHT
                        + "  📊 基本面分析 (Fundamental)"
                        + " " * 20 + "滿分 50 分" + Style.RESET_ALL))
        out.append(line("  " + DIV[: W - 2]))

        # 顯示月營收資料來源（若有）
        rev_data = self.fetcher.monthly_revenue
        if rev_data and rev_data.get("source") == "FinMind":
            period = rev_data.get("period", "")
            out.append(line(
                Style.DIM + f"  ℹ️  月營收資料來源：FinMind（MOPS 無法取得）  期間：{period}"
                + Style.RESET_ALL
            ))

        fund_bd = self.fund["breakdown"]
        for lbl, key, mx in [
            ("  營收成長性",   "revenue", 15),
            ("  EPS 獲利能力", "eps",     15),
            ("  本益比 P/E",   "pe",      10),
            ("  ROE 效益",     "roe",     10),
        ]:
            sc, _, detail = fund_bd[key]
            bar = _bar(sc, mx)
            out.append(line(
                _dpad(lbl, 18) + f"{sc:>2}/{mx:<2} {bar}  "
                + Style.DIM + detail + Style.RESET_ALL
            ))

        out.append(line())
        out.append(line(
            "  基本面小計："
            + Fore.GREEN + Style.BRIGHT + f"{fund_score:>3} / 50" + Style.RESET_ALL
        ))

        # ── 技術面 ──────────────────────────────────────────────────────────
        out.append(MID)
        out.append(line(Fore.MAGENTA + Style.BRIGHT
                        + "  📈 技術面分析 (Technical)"
                        + " " * 21 + "滿分 50 分" + Style.RESET_ALL))
        out.append(line("  " + DIV[: W - 2]))

        tech_bd = self.tech["breakdown"]
        for lbl, key, mx in [
            ("  均線趨勢 MA", "ma",       20),
            ("  MACD & RSI",  "momentum", 15),
            ("  量價關係",     "volume",   15),
        ]:
            sc, _, detail = tech_bd[key]
            bar = _bar(max(sc, 0), mx)
            vol_note = "  ⚠️ 倒扣 -10" if sc < 0 else ""
            score_str = (
                Fore.RED + f"{sc:>3}/{mx:<2}" + Style.RESET_ALL
                if sc < 0
                else f"{sc:>3}/{mx:<2}"
            )
            out.append(line(
                _dpad(lbl, 18) + f"{score_str} {bar}  "
                + Style.DIM + detail + vol_note + Style.RESET_ALL
            ))

        out.append(line())
        out.append(line(
            "  技術面小計："
            + Fore.MAGENTA + Style.BRIGHT + f"{tech_score:>3} / 50" + Style.RESET_ALL
        ))

        # ── 三大法人 ─────────────────────────────────────────────────────────
        out.append(MID)
        insti_title_color = Fore.YELLOW + Style.BRIGHT
        out.append(line(insti_title_color
                        + "  🏦 三大法人動向 (Institutional)"
                        + " " * 17 + "滿分 20 分" + Style.RESET_ALL))
        out.append(line("  " + DIV[: W - 2]))

        insti_bd = self.insti["breakdown"]
        if self.insti["available"]:
            insti_date   = self.insti.get("date", "")
            insti_source = self.insti.get("source", "")
            date_display = f"{insti_date[:4]}/{insti_date[4:6]}/{insti_date[6:]}" if len(insti_date) == 8 else insti_date
            out.append(line(
                Style.DIM + f"  資料日期：{date_display}  來源：{insti_source}" + Style.RESET_ALL
            ))

            for lbl, key, mx in [
                ("  外資", "foreign", config.MAX_INSTI_FOREIGN),
                ("  投信", "trust",   config.MAX_INSTI_TRUST),
                ("  自營", "dealer",  config.MAX_INSTI_DEALER),
            ]:
                sc, _, detail, net = insti_bd[key]
                lots = net // 1000
                lot_str = f"{lots:+,} 張" if net != 0 else "持平"
                bar = _bar(sc, mx)
                out.append(line(
                    _dpad(lbl, 8) + f"{sc:>2}/{mx:<2} {bar}  "
                    + Style.DIM + detail + Style.RESET_ALL
                    + "  (" + (Fore.GREEN if lots > 0 else Fore.RED if lots < 0 else Fore.WHITE)
                    + f"{lot_str}" + Style.RESET_ALL + ")"
                ))

            total_lots = self.insti["total_net"] // 1000
            lot_color  = Fore.GREEN if total_lots > 0 else Fore.RED if total_lots < 0 else Fore.WHITE
            adj = self.insti["adjustment"]
            adj_str = f"+{adj}" if adj >= 0 else str(adj)
            out.append(line())
            out.append(line(
                "  法人小計："
                + insti_title_color + f"{self.insti['total']:>3} / 20" + Style.RESET_ALL
                + "   三大合計："
                + lot_color + f"{total_lots:+,} 張" + Style.RESET_ALL
                + "   總分調整："
                + (Fore.GREEN if adj > 0 else Fore.RED if adj < 0 else Style.DIM)
                + f"({adj_str} 分)" + Style.RESET_ALL
            ))
        else:
            out.append(line(
                Style.DIM + "  法人買賣超資料無法取得（TWSE/TPEX/FinMind 均失敗），不影響總分。"
                + Style.RESET_ALL
            ))

        # ── 綜合判斷 ─────────────────────────────────────────────────────────
        out.append(MID)
        out.append(line(
            "  綜合得分 (信心指數)："
            + rec_col + Style.BRIGHT + f"{total_score}%" + Style.RESET_ALL
            + "  " + _pct_bar(total_score)
        ))
        adj = self.insti["adjustment"]
        adj_str = f"+{adj}" if adj >= 0 else str(adj)
        score_formula = f"  📐 計分：基本面 {fund_score}/50 + 技術面 {tech_score}/50 + 法人調整 ({adj_str})"
        out.append(line(Style.DIM + score_formula + Style.RESET_ALL))
        out.append(line())
        out.append(line(
            "  💡 系統判定："
            + rec_col + Style.BRIGHT + rec_label + Style.RESET_ALL
        ))
        out.append(line(f"  信心指數：{confidence}"))

        # ── 診斷說明 ─────────────────────────────────────────────────────────
        out.append(MID)
        out.append(line(Fore.YELLOW + "  📝 診斷說明" + Style.RESET_ALL))
        out.append(line("  " + DIV[: W - 2]))

        diag_fund = self._build_fund_diagnosis(fund_bd, fund_score)
        diag_tech = self._build_tech_diagnosis(tech_bd, tech_score)
        out.append(line(f"  1. 基本面：{diag_fund}"))
        out.append(line(f"  2. 技術面：{diag_tech}"))

        # ── 目標價格 ─────────────────────────────────────────────────────────
        out.append(MID)
        out += self._build_price_target_section(line, DIV, W)

        out.append(line())
        out.append(line(
            Style.DIM + "  ⚠  本報告僅供參考，不構成投資建議。投資前請做好風險管理。"
            + Style.RESET_ALL
        ))
        out.append(BOT)
        out.append("")

        print("\n".join(out))

    # ── 私有：目標價格區塊 ────────────────────────────────────────────────────

    def _build_price_target_section(self, line, DIV: str, W: int) -> list:
        pt = self.price_target
        rows = []

        cur   = pt["current_price"]
        t_low = pt["target_low"]
        t_hi  = pt["target_high"]
        u_lo  = pt["upside_low_pct"]
        u_hi  = pt["upside_high_pct"]
        strat = pt["strategy"]

        # 顏色依策略
        score = pt["total_score"]
        if score >= 60:
            sc = Fore.YELLOW + Style.BRIGHT
        elif score >= 40:
            sc = Fore.WHITE
        else:
            sc = Fore.CYAN

        rows.append(line(Fore.YELLOW + "  🎯 目標價格建議" + Style.RESET_ALL))
        rows.append(line("  " + DIV[: W - 2]))

        # 現價 + 策略
        rows.append(line(
            f"  現價：{sc}{cur:>8.2f} 元{Style.RESET_ALL}"
            f"   操作策略：{sc + Style.BRIGHT}{strat}{Style.RESET_ALL}"
        ))

        # 目標區間
        sign_lo = "+" if u_lo >= 0 else ""
        sign_hi = "+" if u_hi >= 0 else ""
        rows.append(line(
            f"  目標區間：{sc + Style.BRIGHT}"
            f"{t_low:>8.2f} ~ {t_hi:>8.2f} 元"
            f"{Style.RESET_ALL}"
            f"  ({sign_lo}{u_lo:.1f}% ~ {sign_hi}{u_hi:.1f}%)"
        ))

        # P/E 估算目標
        if pt["pe_target"] and pt["fair_pe"] and pt["eps"]:
            rows.append(line(
                f"  P/E 估算目標：{sc + Style.BRIGHT}{pt['pe_target']:>8.2f} 元"
                f"{Style.RESET_ALL}"
                f"  (EPS {pt['eps']:.2f} × Fair P/E {pt['fair_pe']:.1f}x)"
            ))
        else:
            rows.append(line(
                Style.DIM + "  P/E 估算目標：財務資料不足，無法計算" + Style.RESET_ALL
            ))

        rows.append(line("  " + DIV[: W - 2]))

        # 技術壓力位
        rows.append(line(
            f"  技術壓力參考："
            f"  20日高 {pt['high_20']:.2f}"
            f"  │  60日高 {pt['high_60']:.2f}"
            f"  │  52週高 {pt['high_252']:.2f}"
        ))

        # 停損
        if pt["stop_loss"] and pt["stop_pct"]:
            rows.append(line(
                f"  建議停損：{Fore.RED + Style.BRIGHT}{pt['stop_loss']:>8.2f} 元"
                f"{Style.RESET_ALL}"
                f"  ({pt['stop_pct']*100:.0f}%，跌破請出場)"
            ))
        else:
            rows.append(line(
                Style.DIM + "  建議停損：當前訊號偏空，不建議持有" + Style.RESET_ALL
            ))

        return rows

    # ── 私有：診斷文字 ────────────────────────────────────────────────────────

    def _build_fund_diagnosis(self, bd: dict, total: int) -> str:
        parts = []
        rev_sc  = bd["revenue"][0]
        eps_sc  = bd["eps"][0]
        pe_sc   = bd["pe"][0]
        roe_sc  = bd["roe"][0]

        if rev_sc == 15:
            parts.append("營收雙位數成長動能強")
        elif rev_sc == 5:
            parts.append("營收小幅成長")
        else:
            parts.append("營收動能待觀察")

        if eps_sc == 15:
            parts.append("EPS 成長趨勢明確")
        elif eps_sc >= 10:
            parts.append("EPS 正值穩定")
        else:
            parts.append("獲利能力偏弱")

        if roe_sc == 10:
            parts.append("ROE 高效益")
        elif roe_sc == 5:
            parts.append("ROE 合格")

        if pe_sc == 0:
            parts.append("本益比偏高需留意")

        if total >= 40:
            return "、".join(parts) + "，基本面具底氣。"
        return "、".join(parts) + "，基本面仍有隱憂。"

    def _build_tech_diagnosis(self, bd: dict, total: int) -> str:
        parts = []
        ma_sc  = bd["ma"][0]
        mom_sc = bd["momentum"][0]
        vol_sc = bd["volume"][0]

        if ma_sc >= 20:
            parts.append("均線多頭排列強勁")
        elif ma_sc >= 15:
            parts.append("均線多頭排列")
        elif ma_sc >= 10:
            parts.append("站上月線，趨勢偏多")
        else:
            parts.append("跌破均線，趨勢偏空")

        if mom_sc == 15:
            parts.append("RSI 與 MACD 同步發動")
        elif mom_sc >= 8:
            parts.append("動能指標偏強但需觀察")
        elif mom_sc == 0:
            parts.append("超買或 MACD 轉空")
        else:
            parts.append("動能偏弱")

        if vol_sc < 0:
            parts.append("量增價跌警示需謹慎")
        elif vol_sc >= 15:
            parts.append("量價突破強勁")
        elif vol_sc >= 10:
            parts.append("量能配合良好")

        return "，".join(parts) + "。"
