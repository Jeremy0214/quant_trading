"""
monitor.py
Real-time signal monitor — polls Binance every CHECK_INTERVAL_SECONDS
and sends a Discord alert when a NEW signal appears on a closed 4H candle.

How "new signal" is determined
───────────────────────────────
Only the last CLOSED candle (iloc[-2]) is evaluated each cycle; the live
(currently-forming) candle is excluded to prevent intra-bar RSI/body-ratio
fluctuations from generating spurious alerts.

For each symbol the timestamp of the last alerted closed candle is stored.
A signal is considered "new" only when its candle timestamp is strictly newer
than the previously alerted one, guaranteeing at most ONE alert per 4H candle
per symbol.

Usage
─────
    python monitor.py

Press Ctrl+C to stop.

Setup
─────
1. Open config.py and fill in DISCORD_WEBHOOK_URL
2. (Optional) edit MONITOR_SYMBOLS / MONITOR_TIMEFRAME / CHECK_INTERVAL_SECONDS
"""

import logging
import sys
import time
import warnings
from datetime import datetime, timezone

warnings.filterwarnings("ignore")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-8s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler("monitor.log", encoding="utf-8"),
    ],
)
log = logging.getLogger(__name__)

import config  # noqa: E402
from alerts.discord                import send_signal_alert, send_startup_message, send_exit_alert
from backtest.engine               import calculate_atr
from data.fetcher                  import fetch_ohlcv
from indicators.ma_ema             import add_ma_ema
from indicators.rsi                import add_rsi
from indicators.smc                import add_smc
from indicators.fvg                import detect_fvg
from strategy.combined_strategy    import generate_signals
from tracker.trade_tracker         import register_trade, check_open_trades, get_summary


# Higher-timeframe mapping for TF confluence (Condition D)
_HTF_MAP: dict[str, str] = {
    "15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w",
}


def _fetch_htf_trend(symbol: str, timeframe: str) -> "pd.Series | None":
    """
    Fetch the next-higher timeframe and return its EMA_200 trend
    (True = close > EMA_200, i.e. bullish).  Returns None on failure.
    """
    htf = _HTF_MAP.get(timeframe.lower())
    if htf is None:
        log.debug("No HTF mapping for '%s'; TF confluence skipped.", timeframe)
        return None
    try:
        htf_df = fetch_ohlcv(symbol, htf, limit=250)
        htf_df = add_ma_ema(htf_df)
        return htf_df["trend_up"]
    except Exception as exc:
        log.warning("HTF trend fetch failed (%s → %s): %s", timeframe, htf, exc)
        return None


def _run_pipeline(symbol: str, timeframe: str, limit: int):
    """Fetch data and run full indicator + signal pipeline. Returns DataFrame."""
    df = fetch_ohlcv(symbol, timeframe, limit)
    df = add_ma_ema(df)
    df = add_rsi(df)
    df = add_smc(df)
    df = detect_fvg(df)
    htf_trend = _fetch_htf_trend(symbol, timeframe)
    df = generate_signals(df, htf_trend=htf_trend)
    return df


def _check_symbol(
    symbol: str,
    timeframe: str,
    limit: int,
    last_alerted: dict,
    webhook_urls: list,
) -> None:
    """
    1. Check OPEN trades for SL / TP hits (using current price).
    2. Detect new signals and send Discord alert + register trade.
    """
    try:
        df = _run_pipeline(symbol, timeframe, limit)
    except Exception as exc:
        log.error("[%s] Data fetch / indicator error: %s", symbol, exc)
        return

    current_price = float(df["close"].iloc[-1])

    # ── Step 1 : check if any open trades have hit SL / TP ───────────────────
    closed_trades = check_open_trades(symbol, current_price)
    for trade in closed_trades:
        emoji  = "🎯" if trade["result"] == "TP" else "🛑"
        log.info(
            "[%s] %s %s hit  |  entry=%.2f  exit=%.2f  pnl=%+.2f%%  id=%s",
            symbol, emoji, trade["result"],
            trade["entry_price"], trade["exit_price"],
            trade["pnl_pct"], trade["id"],
        )
        send_exit_alert(trade, webhook_urls)

    # ── Step 2 : detect new signal ────────────────────────────────────────────
    # Only evaluate the last CLOSED candle (iloc[-1] is the live/unfinished bar).
    # This prevents the same partially-formed candle from re-triggering alerts
    # as its RSI / body ratio changes intra-bar, and guarantees at most one
    # alert per closed 4H candle per symbol.
    latest_ts  = df.index[-2]
    latest_row = df.iloc[-2]

    if latest_row["signal"] == 0:
        log.info("[%s] No signal on last closed candle (%s).", symbol, latest_ts)
        return

    direction = "LONG" if latest_row["signal"] == 1 else "SHORT"

    if last_alerted.get(symbol) == latest_ts:
        log.info(
            "[%s] Latest signal (%s @ %s) already alerted — skipping.",
            symbol, direction, latest_ts,
        )
        return

    # Compute SL / TP from ATR
    atr_val = float(calculate_atr(df).iloc[-1])
    entry   = float(latest_row["close"])

    if latest_row["signal"] == 1:   # Long
        stop_loss   = entry - atr_val * config.STOP_LOSS_ATR_MULT
        take_profit = entry + atr_val * config.TAKE_PROFIT_ATR_MULT
    else:                           # Short
        stop_loss   = entry + atr_val * config.STOP_LOSS_ATR_MULT
        take_profit = entry - atr_val * config.TAKE_PROFIT_ATR_MULT

    log.info(
        "[%s] NEW %s signal  |  close=%.2f  SL=%.2f  TP=%.2f  RSI=%.1f  strength=%d/5  candle=%s",
        symbol, direction, entry, stop_loss, take_profit,
        latest_row["RSI"], int(latest_row["signal_strength"]), latest_ts,
    )

    sent = send_signal_alert(
        symbol=symbol,
        timeframe=timeframe,
        row=latest_row,
        webhook_url=webhook_urls,
        stop_loss=stop_loss,
        take_profit=take_profit,
    )

    if sent:
        last_alerted[symbol] = latest_ts
        log.info("[%s] Discord alert sent successfully.", symbol)

        # Register in trade journal (deduplication is handled inside)
        trade_id = register_trade(
            symbol=symbol,
            timeframe=timeframe,
            direction=direction,
            entry_price=entry,
            stop_loss=stop_loss,
            take_profit=take_profit,
            signal_time=latest_ts,
        )
        log.info("[%s] Trade registered in journal  id=%s", symbol, trade_id)
    else:
        log.warning("[%s] Discord alert FAILED — will retry next cycle.", symbol)


def _log_summary() -> None:
    """Print a brief win-rate / P&L summary from the live trade journal."""
    summary = get_summary()
    if "message" in summary:
        log.info("[STATS] %s", summary["message"])
        return
    log.info(
        "[STATS] Closed=%d  Open=%d  WinRate=%.1f%%  TotalPnL=%+.2f%%  PF=%.2f",
        summary["total_closed"], summary["open_trades"],
        summary["win_rate"] * 100,
        summary["total_pnl_pct"],
        summary["profit_factor"],
    )
    for sym, s in summary.get("by_symbol", {}).items():
        log.info(
            "[STATS]   %s  trades=%d  wins=%d  WinRate=%.1f%%  PnL=%+.2f%%",
            sym, s["trades"], s["wins"], s["win_rate"] * 100, s["total_pnl_pct"],
        )


def main() -> None:
    symbols   = config.MONITOR_SYMBOLS
    timeframe = config.MONITOR_TIMEFRAME
    limit     = config.MONITOR_LIMIT
    interval  = config.CHECK_INTERVAL_SECONDS

    # Collect all configured webhook URLs into one list (skip blanks)
    webhook_urls = [
        u for u in [
            getattr(config, "DISCORD_WEBHOOK_URL",  ""),
            getattr(config, "DISCORD_WEBHOOK_URL_2", ""),
        ]
        if u and u.strip()
    ]

    if not webhook_urls:
        log.warning(
            "No Discord webhook URLs configured in config.py. "
            "Signals will be logged to console only."
        )

    log.info("=" * 60)
    log.info("  SMC + FVG + EMA + RSI  —  Real-time Monitor")
    log.info("  Symbols   : %s", "  |  ".join(symbols))
    log.info("  Timeframe : %s", timeframe.upper())
    log.info("  Interval  : %ds  (~%d min)", interval, interval // 60)
    log.info("  Webhooks  : %d channel(s) configured", len(webhook_urls))
    log.info("=" * 60)

    send_startup_message(symbols, timeframe, webhook_urls)

    # Track last alerted candle timestamp per symbol
    last_alerted: dict = {}
    poll_count = 0

    # ── Warm-up scan: record existing signals WITHOUT sending alerts ──────────
    log.info("Warm-up scan: recording existing signals to suppress on first poll…")
    for symbol in symbols:
        try:
            df = _run_pipeline(symbol, timeframe, limit)
            # Warm-up mirrors live detection: only check the last closed candle
            if df.iloc[-2]["signal"] != 0:
                last_alerted[symbol] = df.index[-2]
                log.info(
                    "[%s] Warm-up: existing signal suppressed @ %s",
                    symbol, df.index[-2],
                )
        except Exception as exc:
            log.warning("[%s] Warm-up scan error: %s", symbol, exc)
    log.info("Warm-up complete. Only NEW signals from this point will be alerted.\n")

    # ── Main polling loop ─────────────────────────────────────────────────────
    while True:
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        log.info("── Polling at %s ──", now)

        for symbol in symbols:
            _check_symbol(symbol, timeframe, limit, last_alerted, webhook_urls)

        # Print running stats every 12 cycles (~1 hour with 5-min interval)
        poll_count += 1
        if poll_count % 12 == 0:
            _log_summary()

        log.info("Next check in %d seconds. Press Ctrl+C to stop.\n", interval)

        try:
            time.sleep(interval)
        except KeyboardInterrupt:
            log.info("Monitor stopped by user.")
            sys.exit(0)


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log.info("Monitor stopped.")
