"""
discord_notifier.py — Discord Webhook 通知模組

將股票推薦結果以美觀的 Embed 格式傳送到 Discord 頻道。
"""

import logging
from datetime import datetime
from typing import List

import pytz
import requests

logger = logging.getLogger(__name__)

# 評分標籤與 Embed 顏色
_SCORE_TIERS = [
    (10, "🔥 強力買入", 0xFF4500),
    (7,  "📈 建議買入", 0x00C853),
    (5,  "👀 值得關注", 0xFFD600),
    (0,  "⏭️  觀望",   0x808080),
]

_TW_COLOR = 0xE8192C   # 台灣國旗紅
_US_COLOR = 0x3C3B6E   # 美國國旗藍
_HEADER_COLOR = 0x5865F2  # Discord blurple


def _get_tier(score: int):
    """依據評分取得 (標籤, 顏色)。"""
    for threshold, label, color in _SCORE_TIERS:
        if score >= threshold:
            return label, color
    return "⏭️  觀望", 0x808080


def _fmt_price(price: float, market: str) -> str:
    if market == "TW":
        return f"NT$ {price:,.2f}"
    return f"$ {price:,.2f}"


def _build_field(stock: dict, rank: int) -> dict:
    """建立單一股票的 Discord Embed field。"""
    label, _ = _get_tier(stock["score"])
    price_str = _fmt_price(stock["price"], stock["market"])
    chg = stock["change_pct"]
    chg_emoji = "🟢" if chg >= 0 else "🔴"
    chg_str = f"+{chg:.2f}%" if chg >= 0 else f"{chg:.2f}%"

    signals_str = " ｜ ".join(stock["signals"]) if stock["signals"] else "無特殊信號"
    rsi_line = f"\n📉 RSI: {stock['rsi']}" if stock.get("rsi") is not None else ""

    name = f"#{rank}  {stock['name']}（{stock['ticker']}）"
    value = (
        f"💰 **{price_str}** {chg_emoji} {chg_str}\n"
        f"🎯 評分：**{stock['score']}/12**  {label}\n"
        f"📊 {signals_str}"
        f"{rsi_line}"
    )
    return {"name": name, "value": value, "inline": False}


def send_discord_recommendations(
    webhook_url: str,
    tw_results: List[dict],
    us_results: List[dict],
) -> bool:
    """
    透過 Discord Webhook 傳送今日股票推薦。

    Args:
        webhook_url: Discord Webhook URL
        tw_results:  台股推薦清單
        us_results:  美股推薦清單

    Returns:
        True if 成功, False if 失敗
    """
    now_tw = datetime.now(pytz.timezone("Asia/Taipei"))
    weekdays_zh = ["週一", "週二", "週三", "週四", "週五", "週六", "週日"]
    weekday_str = weekdays_zh[now_tw.weekday()]
    date_str = now_tw.strftime(f"%Y 年 %m 月 %d 日（{weekday_str}）")

    embeds = []

    # ── 標題 Embed ─────────────────────────────────────────
    embeds.append({
        "title": "📊  每日股票投顧推薦",
        "description": (
            f"📅 日期：{date_str}\n"
            f"🇹🇼 台股推薦：**{len(tw_results)}** 檔\n"
            f"🇺🇸 美股推薦：**{len(us_results)}** 檔\n\n"
            "**評分說明**\n"
            "🔥 10-12 強力買入　📈 7-9 建議買入　👀 5-6 值得關注\n\n"
            "⚠️ *本推薦僅依技術分析自動產生，投資有風險，請自行評估後操作*"
        ),
        "color": _HEADER_COLOR,
    })

    # ── 台股 Embed ─────────────────────────────────────────
    if tw_results:
        fields = [_build_field(s, i + 1) for i, s in enumerate(tw_results)]
        embeds.append({
            "title": "🇹🇼  台股推薦",
            "color": _TW_COLOR,
            "fields": fields[:10],
        })
    else:
        embeds.append({
            "title": "🇹🇼  台股推薦",
            "description": "⚠️ 今日無符合條件的台股推薦（評分需 ≥ 5 分）",
            "color": _TW_COLOR,
        })

    # ── 美股 Embed ─────────────────────────────────────────
    if us_results:
        fields = [_build_field(s, i + 1) for i, s in enumerate(us_results)]
        embeds.append({
            "title": "🇺🇸  美股推薦",
            "color": _US_COLOR,
            "fields": fields[:10],
        })
    else:
        embeds.append({
            "title": "🇺🇸  美股推薦",
            "description": "⚠️ 今日無符合條件的美股推薦（評分需 ≥ 5 分）",
            "color": _US_COLOR,
        })

    payload = {
        "content": "📢 **每日股票投顧報告來了！**",
        "embeds": embeds[:10],  # Discord 限制每則訊息最多 10 個 Embed
    }

    try:
        resp = requests.post(webhook_url, json=payload, timeout=15)
        resp.raise_for_status()
        logger.info(f"Discord 訊息傳送成功 (HTTP {resp.status_code})")
        return True
    except requests.exceptions.HTTPError as exc:
        logger.error(
            f"Discord Webhook HTTP 錯誤: {exc.response.status_code} — {exc.response.text}"
        )
    except requests.exceptions.RequestException as exc:
        logger.error(f"Discord Webhook 連線失敗: {exc}")

    return False
