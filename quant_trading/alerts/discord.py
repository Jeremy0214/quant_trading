"""
alerts/discord.py
Send trading signal alerts to a Discord channel via Webhook.

Embed colour coding
───────────────────
Green  (#26a69a)  LONG  signal
Red    (#ef5350)  SHORT signal
"""

import json
import logging
from datetime import datetime, timezone

import requests

logger = logging.getLogger(__name__)

# Embed accent colours (decimal)
_COLOUR_LONG  = 0x26A69A   # teal
_COLOUR_SHORT = 0xEF5350   # red


def _build_embed(
    symbol: str,
    timeframe: str,
    row,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> dict:
    """Build a Discord embed payload from a signal row (pandas Series)."""
    is_long    = int(row["signal"]) == 1
    direction  = "🟢  做多  ▲" if is_long else "🔴  做空  ▼"
    colour     = _COLOUR_LONG if is_long else _COLOUR_SHORT
    strength   = int(row["signal_strength"])

    # ── Condition breakdown ────────────────────────────────────────────────
    from config import EMA_SHORT, EMA_LONG, EMA_TREND

    trend_label = (
        f"📈 上升趨勢（收盤高於 EMA {EMA_TREND}）"
        if row["trend_up"]
        else f"📉 下降趨勢（收盤低於 EMA {EMA_TREND}）"
    )
    ema_label = (
        f"EMA {EMA_SHORT} > EMA {EMA_LONG}（短期動能向上 ↑）"
        if row[f"EMA_{EMA_SHORT}"] > row[f"EMA_{EMA_LONG}"]
        else f"EMA {EMA_SHORT} < EMA {EMA_LONG}（短期動能向下 ↓）"
    )
    rsi_val   = row["RSI"]
    rsi_label = f"{rsi_val:.1f}"
    if rsi_val > 70:
        rsi_label += "  ⚠️ 超買區間"
    elif rsi_val < 30:
        rsi_label += "  ⚠️ 超賣區間"

    bos_ok  = "✅ 確認" if (row.get("bos_bullish") if is_long else row.get("bos_bearish")) else "—"
    ob_ok   = "✅ 確認" if (row.get("ob_bullish")  if is_long else row.get("ob_bearish"))  else "—"
    fvg_ok  = (
        "✅ 未填補看漲缺口"
        if is_long  and row.get("fvg_bullish") and not row.get("fvg_bull_filled")
        else "✅ 未填補看空缺口"
        if not is_long and row.get("fvg_bearish") and not row.get("fvg_bear_filled")
        else "—"
    )

    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    entry   = float(row["close"])

    # ── SL / TP display ───────────────────────────────────────────────────────
    if stop_loss is not None and take_profit is not None:
        rr_ratio = abs(take_profit - entry) / abs(entry - stop_loss) if entry != stop_loss else 0
        sl_label = f"`${stop_loss:,.2f}`  ({(stop_loss - entry) / entry * 100:.2f}%)"
        tp_label = f"`${take_profit:,.2f}`  (+{(take_profit - entry) / entry * 100:.2f}%)"
        rr_label = f"`1 : {rr_ratio:.1f}`"
    else:
        sl_label = "—"
        tp_label = "—"
        rr_label = "—"

    embed = {
        "title": f"{direction}  —  {symbol}  {timeframe.upper()}",
        "color": colour,
        "fields": [
            {
                "name": "💰 進場價格",
                "value": f"`${entry:,.2f}`",
                "inline": True,
            },
            {
                "name": "📊 RSI（14）",
                "value": f"`{rsi_label}`",
                "inline": True,
            },
            {
                "name": "⭐ 訊號強度",
                "value": f"`{strength} / 6`",
                "inline": True,
            },
            {
                "name": "🛑 止損點位",
                "value": sl_label,
                "inline": True,
            },
            {
                "name": "🎯 止盈點位",
                "value": tp_label,
                "inline": True,
            },
            {
                "name": "⚖️ 風報比",
                "value": rr_label,
                "inline": True,
            },
            {
                "name": "📉 主趨勢",
                "value": trend_label,
                "inline": False,
            },
            {
                "name": "〰️ 短期動能",
                "value": ema_label,
                "inline": False,
            },
            {
                "name": "🏛️ SMC — 市場結構突破（BOS）",
                "value": bos_ok,
                "inline": True,
            },
            {
                "name": "🧱 SMC — 機構掛單區（OB）",
                "value": ob_ok,
                "inline": True,
            },
            {
                "name": "⚡ 失衡缺口（FVG）",
                "value": fvg_ok,
                "inline": True,
            },
        ],
        "footer": {
            "text": f"SMC + FVG + EMA + RSI 量化策略  |  {now_utc}",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    return embed


def send_signal_alert(
    symbol: str,
    timeframe: str,
    row,
    webhook_url: str,
    stop_loss: float | None = None,
    take_profit: float | None = None,
) -> bool:
    """
    POST a signal embed to Discord.

    Parameters
    ----------
    symbol      : e.g. "BTC/USDT"
    timeframe   : e.g. "4h"
    row         : pandas Series for the signal bar
    webhook_url : Discord webhook URL
    stop_loss   : computed SL price level (optional)
    take_profit : computed TP price level (optional)

    Returns True on success, False on failure.
    """
    if not webhook_url:
        logger.warning("DISCORD_WEBHOOK_URL is empty — alert skipped.")
        return False

    embed   = _build_embed(symbol, timeframe, row, stop_loss, take_profit)
    payload = {"embeds": [embed]}

    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code in (200, 204):
            logger.info("Discord alert sent: %s %s", symbol, timeframe)
            return True
        else:
            logger.error("Discord webhook error %s: %s", resp.status_code, resp.text)
            return False
    except requests.RequestException as exc:
        logger.error("Discord webhook request failed: %s", exc)
        return False


def send_startup_message(symbols: list[str], timeframe: str, webhook_url: str) -> None:
    """Send a simple text message when the monitor starts."""
    if not webhook_url:
        return

    symbol_list = "  |  ".join(symbols)
    payload = {
        "content": (
            f"🤖  **監控已啟動**\n"
            f"監控幣種：`{symbol_list}`  —  週期：`{timeframe.upper()}`\n"
            f"策略：SMC + FVG + EMA + RSI 量化策略"
        )
    }
    try:
        requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
    except requests.RequestException as exc:
        logger.warning("Could not send startup message: %s", exc)


def send_exit_alert(trade: dict, webhook_url: str) -> bool:
    """
    Send a Discord notification when a trade hits TP or SL.

    Parameters
    ----------
    trade       : dict from trade_tracker (closed trade record)
    webhook_url : Discord webhook URL
    """
    if not webhook_url:
        return False

    is_tp    = trade["result"] == "TP"
    is_long  = trade["direction"] == "LONG"
    pnl      = trade["pnl_pct"]

    if is_tp:
        title  = f"🎯  止盈觸發  —  {trade['symbol']}  {trade['timeframe'].upper()}"
        colour = 0x26A69A if pnl >= 0 else 0xEF5350
        emoji  = "✅"
    else:
        title  = f"🛑  止損觸發  —  {trade['symbol']}  {trade['timeframe'].upper()}"
        colour = 0xEF5350
        emoji  = "❌"

    dir_label  = "做多 ▲" if is_long else "做空 ▼"
    pnl_label  = f"`{pnl:+.2f}%`"
    now_utc    = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    embed = {
        "title": title,
        "color": colour,
        "fields": [
            {"name": "📌 方向",   "value": f"`{dir_label}`",                       "inline": True},
            {"name": "💰 進場價", "value": f"`${trade['entry_price']:,.2f}`",       "inline": True},
            {"name": "🚪 出場價", "value": f"`${trade['exit_price']:,.2f}`",        "inline": True},
            {"name": "💹 盈虧",   "value": f"{emoji}  {pnl_label}",                "inline": True},
            {"name": "📋 結果",   "value": f"`{'止盈 TP' if trade['result'] == 'TP' else '止損 SL'}`", "inline": True},
            {"name": "⚖️ 風報比", "value": f"`1 : {trade['rr_ratio']:.1f}`",       "inline": True},
            {"name": "🛑 止損設定","value": f"`${trade['stop_loss']:,.2f}`",        "inline": True},
            {"name": "🎯 止盈設定","value": f"`${trade['take_profit']:,.2f}`",      "inline": True},
            {"name": "🔖 交易編號","value": f"`{trade['id']}`",                     "inline": True},
        ],
        "footer": {
            "text": f"SMC + FVG + EMA + RSI 量化策略  |  {now_utc}",
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    payload = {"embeds": [embed]}
    try:
        resp = requests.post(
            webhook_url,
            data=json.dumps(payload),
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        if resp.status_code in (200, 204):
            logger.info("Exit alert sent: %s %s %s", trade["symbol"], trade["result"], pnl_label)
            return True
        logger.error("Exit alert webhook error %s: %s", resp.status_code, resp.text)
        return False
    except requests.RequestException as exc:
        logger.error("Exit alert request failed: %s", exc)
        return False
