"""
main.py
Entry point — fetch data, compute indicators, generate signals,
run backtest, and render an interactive chart.

Usage
─────
    python main.py
    python main.py --symbol ETH/USDT --timeframe 1h --limit 300
"""

import argparse
import warnings
import webbrowser

warnings.filterwarnings("ignore")

import config  # noqa: E402  (update config before importing sub-modules)


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="SMC + FVG + EMA + RSI Quant Strategy")
    p.add_argument("--symbol",    default=config.SYMBOL,    help="Trading pair, e.g. BTC/USDT")
    p.add_argument("--timeframe", default=config.TIMEFRAME, help="Candle interval, e.g. 4h")
    p.add_argument("--limit",     default=config.LIMIT, type=int, help="Number of candles")
    p.add_argument("--no-browser", action="store_true", help="Skip opening chart in browser")
    return p.parse_args()


def main() -> None:
    args = _parse_args()

    # Allow CLI overrides
    config.SYMBOL    = args.symbol
    config.TIMEFRAME = args.timeframe
    config.LIMIT     = args.limit

    # Late imports so config values are applied first
    from data.fetcher                  import fetch_ohlcv
    from indicators.ma_ema             import add_ma_ema
    from indicators.rsi                import add_rsi
    from indicators.smc                import add_smc
    from indicators.fvg                import detect_fvg
    from strategy.combined_strategy    import generate_signals
    from backtest.engine               import run_backtest
    from visualization.chart           import plot_chart

    print("=" * 55)
    print(f"  SMC + FVG + EMA + RSI Quantitative Strategy")
    print(f"  Symbol: {config.SYMBOL}  |  Timeframe: {config.TIMEFRAME}")
    print("=" * 55)

    # ── 1. Data ───────────────────────────────────────────────────────────────
    print("\n[1/5] Fetching data from Binance …")
    df = fetch_ohlcv()
    print(f"      {len(df)} candles  |  {df.index[0]}  →  {df.index[-1]}")

    # ── 2. Indicators ─────────────────────────────────────────────────────────
    print("\n[2/5] Computing indicators …")
    df = add_ma_ema(df)
    print("      ✓ MA / EMA (20 / 50 / 200)")
    df = add_rsi(df)
    print("      ✓ RSI (14)")
    df = add_smc(df)
    print("      ✓ SMC  — swing pivots, BOS, CHoCH, Order Blocks")
    df = detect_fvg(df)
    print("      ✓ FVG  — bullish / bearish imbalances")

    # ── 3. Signals ────────────────────────────────────────────────────────────
    print("\n[3/5] Generating trading signals …")

    # Fetch higher-TF trend for TF confluence (Condition D)
    _htf_map = {"15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
    _htf_tf   = _htf_map.get(config.TIMEFRAME.lower())
    htf_trend = None
    if _htf_tf:
        try:
            htf_df = fetch_ohlcv(config.SYMBOL, _htf_tf, limit=250)
            htf_df = add_ma_ema(htf_df)
            htf_trend = htf_df["trend_up"]
            print(f"      ✓ HTF trend ({_htf_tf.upper()}) loaded for TF confluence")
        except Exception as _e:
            print(f"      ⚠ HTF trend unavailable ({_e}); Condition D skipped")

    df = generate_signals(df, htf_trend=htf_trend)
    n_long  = (df["signal"] == 1).sum()
    n_short = (df["signal"] == -1).sum()
    print(f"      LONG signals: {n_long}  |  SHORT signals: {n_short}")

    # ── 4. Backtest ───────────────────────────────────────────────────────────
    print("\n[4/5] Running backtest …")
    trades_df, metrics, equity_curve = run_backtest(df)

    print("\n  ── Backtest Results ──────────────────────────────")
    if "message" in metrics:
        print(f"  {metrics['message']}")
    else:
        print(f"  Total trades   : {metrics['total_trades']}")
        print(f"  Win rate       : {metrics['win_rate']:.1%}")
        print(f"  Profit factor  : {metrics['profit_factor']:.2f}")
        print(f"  Total PnL      : ${metrics['total_pnl']:>10,.2f}")
        print(f"  Total return   : {metrics['total_return']:.2f} %")
        print(f"  Max drawdown   : {metrics['max_drawdown']:.2f} %")
        print(f"  Final capital  : ${metrics['final_capital']:>10,.2f}")
        print(f"  Best trade     : ${metrics['best_trade']:>10,.2f}")
        print(f"  Worst trade    : ${metrics['worst_trade']:>10,.2f}")
    print("  " + "─" * 48)

    # ── 5. Chart ──────────────────────────────────────────────────────────────
    print("\n[5/5] Rendering chart …")
    output_file = "chart.html"
    plot_chart(df, trades_df, equity_curve, output_file=output_file)

    if not args.no_browser:
        webbrowser.open(output_file)

    # ── Recent signals ────────────────────────────────────────────────────────
    recent = df[df["signal"] != 0].tail(10)
    if not recent.empty:
        print("\n  ── Recent Signals (latest 10) ────────────────────")
        for ts, row in recent.iterrows():
            direction = "LONG  ▲" if row["signal"] == 1 else "SHORT ▼"
            print(
                f"  {ts}  {direction}  "
                f"close={row['close']:.2f}  "
                f"RSI={row['RSI']:.1f}  "
                f"strength={int(row['signal_strength'])}/5"
            )
        print("  " + "─" * 48)
    else:
        print("\n  No signals in the selected window.")

    print("\nDone.")


if __name__ == "__main__":
    main()
