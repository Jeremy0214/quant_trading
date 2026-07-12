"""
backtest/engine.py
Event-driven backtester with dual take-profit and next-bar-open entry.

Entry  : next bar's open price (eliminates look-ahead bias on signal bar)
Exit   : stop-loss or take-profit evaluated on every subsequent bar's close.
         TP1 (1:1 RR) closes half the position and moves SL to breakeven.
         TP2 (1:2 RR) closes the remaining half.
Risk   : RISK_PER_TRADE % of current equity per trade
Size   : position_size = risk_amount / (entry_open - stop_loss)

result codes
────────────
  SL   full position stopped out (before TP1)
  TP1  first half closed at 1:1 RR; SL moves to breakeven
  TP2  second half closed at 1:2 RR
  BE   remaining half closed at breakeven after TP1 was hit

Returns
───────
trades_df    : DataFrame of exit events (one row per partial/full exit)
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
    sl_mult / tp_mult override config values when provided (ATR fallback only).
    """
    _sl = sl_mult if sl_mult is not None else config.STOP_LOSS_ATR_MULT
    _tp = tp_mult if tp_mult is not None else config.TAKE_PROFIT_ATR_MULT
    _capital_init = float(config.INITIAL_CAPITAL)
    _risk         = config.RISK_PER_TRADE

    df = df.copy()
    df["ATR"] = _atr(df)

    capital  = _capital_init

    # ── Position state ────────────────────────────────────────────────────────
    position      = 0        # 0=flat, 1=long, -1=short
    entry_price   = 0.0
    stop_loss     = 0.0
    take_profit1  = 0.0
    take_profit2  = 0.0
    pos_size      = 0.0      # full position size
    pos_size_half = 0.0      # half position size (TP1 leg and TP2/BE leg)
    tp1_hit       = False    # True once TP1 has been filled
    entry_time    = None

    # ── Pending signal (will enter at NEXT bar's open) ────────────────────────
    pending_signal      = 0
    pending_sl          = np.nan
    pending_tp1         = np.nan
    pending_tp2         = np.nan
    pending_signal_time = None
    risk_amount_pending = 0.0

    trades       = []
    equity_curve = [capital]

    for i in range(1, len(df)):
        open_price = df["open"].iloc[i]
        price      = df["close"].iloc[i]
        atr        = df["ATR"].iloc[i]
        signal     = df["signal"].iloc[i]

        # ── 1. Enter pending signal at this bar's open ────────────────────────
        if position == 0 and pending_signal != 0 and not np.isnan(atr) and atr > 0:
            sl  = pending_sl
            tp1 = pending_tp1
            tp2 = pending_tp2

            if pending_signal == 1:                # Long entry
                risk_per_unit = open_price - sl
                if risk_per_unit > 0:
                    pos_size      = risk_amount_pending / risk_per_unit
                    pos_size_half = pos_size / 2
                    position      = 1
                    entry_price   = open_price
                    stop_loss     = sl
                    take_profit1  = tp1
                    take_profit2  = tp2
                    tp1_hit       = False
                    entry_time    = pending_signal_time

            elif pending_signal == -1:             # Short entry
                risk_per_unit = sl - open_price
                if risk_per_unit > 0:
                    pos_size      = risk_amount_pending / risk_per_unit
                    pos_size_half = pos_size / 2
                    position      = -1
                    entry_price   = open_price
                    stop_loss     = sl
                    take_profit1  = tp1
                    take_profit2  = tp2
                    tp1_hit       = False
                    entry_time    = pending_signal_time

        pending_signal = 0   # consume regardless

        # ── 2. Manage open position (evaluate against bar close) ───────────────
        if position == 1:                          # ── Long ──
            if price <= stop_loss:
                if tp1_hit:                        # remaining half exits at breakeven
                    pnl    = (stop_loss - entry_price) * pos_size_half
                    result = "BE"
                else:                              # full position stopped out
                    pnl    = (stop_loss - entry_price) * pos_size
                    result = "SL"
                capital += pnl
                trades.append(dict(
                    entry_time=entry_time, exit_time=df.index[i],
                    direction="LONG", entry=entry_price,
                    exit=stop_loss, pnl=pnl, result=result,
                ))
                position = 0

            elif not tp1_hit and price >= take_profit1:
                # TP1: close first half, move SL to breakeven
                pnl = (take_profit1 - entry_price) * pos_size_half
                capital += pnl
                trades.append(dict(
                    entry_time=entry_time, exit_time=df.index[i],
                    direction="LONG", entry=entry_price,
                    exit=take_profit1, pnl=pnl, result="TP1",
                ))
                tp1_hit   = True
                stop_loss = entry_price            # breakeven stop

            elif tp1_hit and price >= take_profit2:
                # TP2: close remaining half
                pnl = (take_profit2 - entry_price) * pos_size_half
                capital += pnl
                trades.append(dict(
                    entry_time=entry_time, exit_time=df.index[i],
                    direction="LONG", entry=entry_price,
                    exit=take_profit2, pnl=pnl, result="TP2",
                ))
                position = 0

        elif position == -1:                       # ── Short ──
            if price >= stop_loss:
                if tp1_hit:
                    pnl    = (entry_price - stop_loss) * pos_size_half
                    result = "BE"
                else:
                    pnl    = (entry_price - stop_loss) * pos_size
                    result = "SL"
                capital += pnl
                trades.append(dict(
                    entry_time=entry_time, exit_time=df.index[i],
                    direction="SHORT", entry=entry_price,
                    exit=stop_loss, pnl=pnl, result=result,
                ))
                position = 0

            elif not tp1_hit and price <= take_profit1:
                # TP1: close first half, move SL to breakeven
                pnl = (entry_price - take_profit1) * pos_size_half
                capital += pnl
                trades.append(dict(
                    entry_time=entry_time, exit_time=df.index[i],
                    direction="SHORT", entry=entry_price,
                    exit=take_profit1, pnl=pnl, result="TP1",
                ))
                tp1_hit   = True
                stop_loss = entry_price

            elif tp1_hit and price <= take_profit2:
                # TP2: close remaining half
                pnl = (entry_price - take_profit2) * pos_size_half
                capital += pnl
                trades.append(dict(
                    entry_time=entry_time, exit_time=df.index[i],
                    direction="SHORT", entry=entry_price,
                    exit=take_profit2, pnl=pnl, result="TP2",
                ))
                position = 0

        # ── 3. Detect new signal → store as pending for next bar's open ────────
        if position == 0 and signal != 0 and not np.isnan(atr) and atr > 0:
            close_i = df["close"].iloc[i]
            row_sl  = df["sl_price"].iloc[i]  if "sl_price"  in df.columns else np.nan
            row_tp1 = df["tp1_price"].iloc[i] if "tp1_price" in df.columns else np.nan
            row_tp2 = df["tp2_price"].iloc[i] if "tp2_price" in df.columns else np.nan

            if np.isnan(row_sl) or np.isnan(row_tp1):
                # ATR fallback: compute levels relative to signal bar close
                dist = atr * _sl
                if signal == 1:
                    row_sl  = close_i - dist
                    row_tp1 = close_i + dist * config.TP1_RR
                    row_tp2 = close_i + dist * config.TP2_RR
                else:
                    row_sl  = close_i + dist
                    row_tp1 = close_i - dist * config.TP1_RR
                    row_tp2 = close_i - dist * config.TP2_RR

            if np.isnan(row_tp2):
                row_tp2 = row_tp1   # fallback: match TP1

            # Sanity: SL and TP1 must be on the correct side of close
            valid = (
                (signal == 1  and row_sl < close_i and row_tp1 > close_i)
                or (signal == -1 and row_sl > close_i and row_tp1 < close_i)
            )
            if valid:
                pending_signal      = signal
                pending_sl          = float(row_sl)
                pending_tp1         = float(row_tp1)
                pending_tp2         = float(row_tp2)
                pending_signal_time = df.index[i]
                risk_amount_pending = capital * _risk

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
