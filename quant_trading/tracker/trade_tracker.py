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
    signal_time,                    # pandas Timestamp or datetime
    alert_time=None,
    take_profit_2: float | None = None,
) -> str:
    """
    Register a new open trade.  Returns the trade ID.
    Supports dual take-profit levels (TP1 + TP2).
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
        "id":            str(uuid.uuid4())[:8],
        "symbol":        symbol,
        "timeframe":     timeframe,
        "direction":     direction,
        "entry_price":   round(entry_price, 6),
        "stop_loss":     round(stop_loss,   6),
        "take_profit":   round(take_profit, 6),
        "take_profit_2": round(take_profit_2, 6) if take_profit_2 is not None else None,
        "risk_pct":      round(risk_pct,    4),
        "reward_pct":    round(reward_pct,  4),
        "rr_ratio":      round(rr,          3),
        "signal_time":   sig_ts,
        "alert_time":    str(alert_time or datetime.now(timezone.utc)),
        "tp1_hit":       False,        # True after first TP is reached
        "exit_price":    None,
        "exit_time":     None,
        "result":        "OPEN",
        "pnl_pct":       None,
    }
    trades.append(trade)
    _save(trades)
    return trade["id"]


def check_open_trades(symbol: str, current_price: float) -> list:
    """
    Check all OPEN trades for `symbol` against `current_price`.
    Supports dual take-profit (TP1 partial close → TP2 full close).
    Returns a list of trade-event dicts for closed or partially-closed events.
    """
    trades   = _load()
    events   = []
    modified = False

    for trade in trades:
        if trade["symbol"] != symbol or trade["result"] != "OPEN":
            continue

        entry    = trade["entry_price"]
        sl       = trade["stop_loss"]
        tp1      = trade["take_profit"]
        tp2      = trade.get("take_profit_2")
        tp1_done = trade.get("tp1_hit", False)
        is_long  = trade["direction"] == "LONG"

        # ── Phase 1: waiting for TP1 ────────────────────────────────────────
        if not tp1_done:
            if (is_long and current_price >= tp1) or (not is_long and current_price <= tp1):
                # TP1 hit: partial close (50 %)
                trade["tp1_hit"] = True
                pnl_tp1 = (
                    (tp1 - entry) / entry * 100 if is_long
                    else (entry - tp1) / entry * 100
                )
                events.append({
                    **trade,
                    "result":     "TP1",
                    "exit_price": round(tp1, 6),
                    "exit_time":  str(datetime.now(timezone.utc)),
                    "pnl_pct":    round(pnl_tp1, 4),
                    "note":       "50% position closed at TP1",
                })
                modified = True
                # If no TP2 configured, fully close the trade
                if tp2 is None:
                    trade["result"]     = "TP"
                    trade["exit_price"] = round(tp1, 6)
                    trade["exit_time"]  = str(datetime.now(timezone.utc))
                    trade["pnl_pct"]    = round(pnl_tp1, 4)
                continue

            if (is_long and current_price <= sl) or (not is_long and current_price >= sl):
                pnl = (
                    (sl - entry) / entry * 100 if is_long
                    else (entry - sl) / entry * 100
                )
                trade["result"]     = "SL"
                trade["exit_price"] = round(sl, 6)
                trade["exit_time"]  = str(datetime.now(timezone.utc))
                trade["pnl_pct"]    = round(pnl, 4)
                events.append(dict(trade))
                modified = True

        # ── Phase 2: TP1 already hit, waiting for TP2 or SL ─────────────────
        else:
            if tp2 is not None and (
                (is_long and current_price >= tp2)
                or (not is_long and current_price <= tp2)
            ):
                pnl_tp2 = (
                    (tp2 - entry) / entry * 100 if is_long
                    else (entry - tp2) / entry * 100
                )
                trade["result"]     = "TP"
                trade["exit_price"] = round(tp2, 6)
                trade["exit_time"]  = str(datetime.now(timezone.utc))
                trade["pnl_pct"]    = round(pnl_tp2, 4)
                events.append(dict(trade))
                modified = True

            elif (is_long and current_price <= sl) or (not is_long and current_price >= sl):
                pnl = (
                    (sl - entry) / entry * 100 if is_long
                    else (entry - sl) / entry * 100
                )
                trade["result"]     = "SL_AFTER_TP1"  # partial win
                trade["exit_price"] = round(sl, 6)
                trade["exit_time"]  = str(datetime.now(timezone.utc))
                trade["pnl_pct"]    = round(pnl, 4)
                events.append(dict(trade))
                modified = True

    if modified:
        _save(trades)

    return events


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
