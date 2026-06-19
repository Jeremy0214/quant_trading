"""
tracker/trade_tracker.py
Persistent trade journal for live signal tracking.

每次 monitor.py 發出訊號通知時，會呼叫 register_trade() 寫入一筆記錄。
每次輪詢時，會呼叫 check_open_trades() 判斷止盈/止損是否觸發。
結果永久儲存在 trades_log.json，重啟後不會遺失。

JSON schema (每筆交易)
────────────────────────
{
  "id"          : 短 UUID（8 碼）
  "symbol"      : "BTC/USDT"
  "timeframe"   : "4h"
  "direction"   : "LONG" | "SHORT"
  "entry_price" : float
  "stop_loss"   : float
  "take_profit" : float
  "risk_pct"    : 止損距離 %（負數）
  "reward_pct"  : 止盈距離 %（正數）
  "rr_ratio"    : reward / risk
  "signal_time" : K棒時間 (ISO)
  "alert_time"  : 通知發出時間 (ISO)
  "exit_price"  : float | null
  "exit_time"   : ISO | null
  "result"      : "OPEN" | "TP" | "SL"
  "pnl_pct"     : float | null   實際盈虧 %
}
"""

import json
import uuid
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

TRADES_FILE = Path("trades_log.json")


# ── I/O helpers ───────────────────────────────────────────────────────────────

def _load() -> list:
    if not TRADES_FILE.exists():
        return []
    with TRADES_FILE.open(encoding="utf-8") as f:
        return json.load(f)


def _save(trades: list) -> None:
    with TRADES_FILE.open("w", encoding="utf-8") as f:
        json.dump(trades, f, indent=2, ensure_ascii=False)


# ── Public API ────────────────────────────────────────────────────────────────

def register_trade(
    symbol: str,
    timeframe: str,
    direction: str,
    entry_price: float,
    stop_loss: float,
    take_profit: float,
    signal_time,          # pandas Timestamp or datetime
    alert_time=None,
) -> str:
    """
    Register a new open trade.  Returns the trade ID.
    Skips registration if an identical open trade (same symbol + signal_time)
    already exists (prevents duplicate entries on monitor restart).
    """
    trades = _load()
    sig_ts = str(signal_time)

    # Deduplication guard
    for t in trades:
        if t["symbol"] == symbol and t["signal_time"] == sig_ts and t["result"] == "OPEN":
            return t["id"]

    rr = abs(take_profit - entry_price) / abs(entry_price - stop_loss)

    if direction == "LONG":
        risk_pct   = (stop_loss   - entry_price) / entry_price * 100
        reward_pct = (take_profit - entry_price) / entry_price * 100
    else:
        risk_pct   = (entry_price - stop_loss)   / entry_price * 100
        reward_pct = (entry_price - take_profit) / entry_price * 100

    trade = {
        "id":           str(uuid.uuid4())[:8],
        "symbol":       symbol,
        "timeframe":    timeframe,
        "direction":    direction,
        "entry_price":  round(entry_price, 6),
        "stop_loss":    round(stop_loss,   6),
        "take_profit":  round(take_profit, 6),
        "risk_pct":     round(risk_pct,    4),
        "reward_pct":   round(reward_pct,  4),
        "rr_ratio":     round(rr,          3),
        "signal_time":  sig_ts,
        "alert_time":   str(alert_time or datetime.now(timezone.utc)),
        "exit_price":   None,
        "exit_time":    None,
        "result":       "OPEN",
        "pnl_pct":      None,
    }
    trades.append(trade)
    _save(trades)
    return trade["id"]


def check_open_trades(symbol: str, current_price: float) -> list:
    """
    Check all OPEN trades for `symbol` against `current_price`.
    Closes trades that hit SL or TP; returns a list of newly-closed trades.
    """
    trades   = _load()
    closed   = []
    modified = False

    for trade in trades:
        if trade["symbol"] != symbol or trade["result"] != "OPEN":
            continue

        entry  = trade["entry_price"]
        sl     = trade["stop_loss"]
        tp     = trade["take_profit"]
        hit    = None
        exit_p = None

        if trade["direction"] == "LONG":
            if current_price <= sl:
                hit, exit_p = "SL", sl
            elif current_price >= tp:
                hit, exit_p = "TP", tp
        else:  # SHORT
            if current_price >= sl:
                hit, exit_p = "SL", sl
            elif current_price <= tp:
                hit, exit_p = "TP", tp

        if hit:
            pnl = (
                (exit_p - entry) / entry * 100
                if trade["direction"] == "LONG"
                else (entry - exit_p) / entry * 100
            )
            trade["result"]     = hit
            trade["exit_price"] = round(exit_p, 6)
            trade["exit_time"]  = str(datetime.now(timezone.utc))
            trade["pnl_pct"]    = round(pnl, 4)
            closed.append(dict(trade))   # snapshot before save
            modified = True

    if modified:
        _save(trades)

    return closed


def get_summary() -> dict:
    """Compute win rate and P&L from all closed trades."""
    trades = _load()
    closed = [t for t in trades if t["result"] != "OPEN"]
    open_t = [t for t in trades if t["result"] == "OPEN"]

    if not closed:
        return {
            "total_closed": 0,
            "open_trades":  len(open_t),
            "message":      "No closed trades yet.",
        }

    wins   = [t for t in closed if t["result"] == "TP"]
    losses = [t for t in closed if t["result"] == "SL"]
    total  = len(closed)

    gross_win  = sum(t["pnl_pct"] for t in wins)   if wins   else 0.0
    gross_loss = abs(sum(t["pnl_pct"] for t in losses)) if losses else 0.0

    # Per-symbol breakdown
    by_sym: dict = defaultdict(lambda: {"trades": 0, "wins": 0, "total_pnl_pct": 0.0})
    for t in closed:
        s = t["symbol"]
        by_sym[s]["trades"]        += 1
        by_sym[s]["total_pnl_pct"] += t["pnl_pct"]
        if t["result"] == "TP":
            by_sym[s]["wins"] += 1
    for s in by_sym:
        n = by_sym[s]["trades"]
        by_sym[s]["win_rate"] = round(by_sym[s]["wins"] / n, 4)

    return {
        "total_closed":   total,
        "open_trades":    len(open_t),
        "wins":           len(wins),
        "losses":         len(losses),
        "win_rate":       len(wins) / total,
        "total_pnl_pct":  round(sum(t["pnl_pct"] for t in closed), 4),
        "avg_pnl_pct":    round(sum(t["pnl_pct"] for t in closed) / total, 4),
        "best_trade_pct": round(max(t["pnl_pct"] for t in closed), 4),
        "worst_trade_pct":round(min(t["pnl_pct"] for t in closed), 4),
        "profit_factor":  round(gross_win / gross_loss, 3) if gross_loss > 0 else float("inf"),
        "by_symbol":      dict(by_sym),
    }


def get_open_trades() -> list:
    return [t for t in _load() if t["result"] == "OPEN"]


def get_all_trades() -> list:
    return _load()
