"""
backtest/engine.py
Simple event-driven backtester (one position at a time).

Entry  : signal bar close price  (next-bar open is more conservative but
         this keeps the demo clear; note in production use next open)
Exit   : stop-loss or take-profit evaluated on every subsequent bar's close
Risk   : RISK_PER_TRADE % of current equity per trade
Size   : position_size = risk_amount / (entry - stop_loss)

Returns
───────
trades_df    : DataFrame of completed trades
metrics      : dict of performance statistics
equity_curve : list of equity values (one per bar)
"""

import numpy as np
import pandas as pd

import config


def _atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    hl  = df["high"] - df["low"]
    hpc = (df["high"] - df["close"].shift()).abs()
    lpc = (df["low"]  - df["close"].shift()).abs()
    tr  = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _max_drawdown(curve: list) -> float:
    peak   = curve[0]
    max_dd = 0.0
    for v in curve:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd
    return max_dd * 100.0


def calculate_atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    """Public ATR helper (also used by monitor for SL/TP calculation)."""
    return _atr(df, period)


def run_backtest(
    df: pd.DataFrame,
    sl_mult: float | None = None,
    tp_mult: float | None = None,
):
    """
    sl_mult / tp_mult override config values when provided.
    """
    _sl = sl_mult if sl_mult is not None else config.STOP_LOSS_ATR_MULT
    _tp = tp_mult if tp_mult is not None else config.TAKE_PROFIT_ATR_MULT
    _capital_init = float(config.INITIAL_CAPITAL)
    _risk         = config.RISK_PER_TRADE

    df = df.copy()
    df["ATR"] = _atr(df)

    capital  = _capital_init
    position = 0
    entry_price = 0.0
    stop_loss   = 0.0
    take_profit = 0.0
    pos_size    = 0.0
    entry_time  = None

    trades       = []
    equity_curve = [capital]

    for i in range(1, len(df)):
        price  = df["close"].iloc[i]
        atr    = df["ATR"].iloc[i]
        signal = df["signal"].iloc[i]

        # ── Manage open position ──────────────────────────────────────────────
        if position == 1:                          # Long
            if price <= stop_loss:
                pnl = (stop_loss - entry_price) * pos_size
                capital += pnl
                trades.append(
                    dict(entry_time=entry_time, exit_time=df.index[i],
                         direction="LONG", entry=entry_price,
                         exit=stop_loss, pnl=pnl, result="SL")
                )
                position = 0

            elif price >= take_profit:
                pnl = (take_profit - entry_price) * pos_size
                capital += pnl
                trades.append(
                    dict(entry_time=entry_time, exit_time=df.index[i],
                         direction="LONG", entry=entry_price,
                         exit=take_profit, pnl=pnl, result="TP")
                )
                position = 0

        elif position == -1:                       # Short
            if price >= stop_loss:
                pnl = (entry_price - stop_loss) * pos_size
                capital += pnl
                trades.append(
                    dict(entry_time=entry_time, exit_time=df.index[i],
                         direction="SHORT", entry=entry_price,
                         exit=stop_loss, pnl=pnl, result="SL")
                )
                position = 0

            elif price <= take_profit:
                pnl = (entry_price - take_profit) * pos_size
                capital += pnl
                trades.append(
                    dict(entry_time=entry_time, exit_time=df.index[i],
                         direction="SHORT", entry=entry_price,
                         exit=take_profit, pnl=pnl, result="TP")
                )
                position = 0

        # ── Enter new position ────────────────────────────────────────────────
        if position == 0 and signal != 0 and not np.isnan(atr) and atr > 0:
            risk_amount = capital * _risk

            if signal == 1:                        # Long
                sl = price - atr * _sl
                tp = price + atr * _tp
                risk_per_unit = price - sl
                if risk_per_unit > 0:
                    pos_size    = risk_amount / risk_per_unit
                    position    = 1
                    entry_price = price
                    stop_loss   = sl
                    take_profit = tp
                    entry_time  = df.index[i]

            elif signal == -1:                     # Short
                sl = price + atr * _sl
                tp = price - atr * _tp
                risk_per_unit = sl - price
                if risk_per_unit > 0:
                    pos_size    = risk_amount / risk_per_unit
                    position    = -1
                    entry_price = price
                    stop_loss   = sl
                    take_profit = tp
                    entry_time  = df.index[i]

        equity_curve.append(capital)

    # ── Performance summary ───────────────────────────────────────────────────
    trades_df = pd.DataFrame(trades)

    if trades_df.empty:
        return trades_df, {"message": "No trades executed"}, equity_curve

    n_total  = len(trades_df)
    n_win    = (trades_df["pnl"] > 0).sum()
    total_rr = trades_df["pnl"].sum()

    metrics = {
        "total_trades":   n_total,
        "winning_trades": int(n_win),
        "losing_trades":  int(n_total - n_win),
        "win_rate":       n_win / n_total,
        "total_pnl":      total_rr,
        "avg_pnl":        trades_df["pnl"].mean(),
        "best_trade":     trades_df["pnl"].max(),
        "worst_trade":    trades_df["pnl"].min(),
        "total_return":   (capital - _capital_init) / _capital_init * 100,
        "final_capital":  capital,
        "max_drawdown":   _max_drawdown(equity_curve),
    }

    # Profit factor
    gross_profit = trades_df.loc[trades_df["pnl"] > 0, "pnl"].sum()
    gross_loss   = trades_df.loc[trades_df["pnl"] < 0, "pnl"].abs().sum()
    metrics["profit_factor"] = gross_profit / gross_loss if gross_loss > 0 else float("inf")

    return trades_df, metrics, equity_curve
