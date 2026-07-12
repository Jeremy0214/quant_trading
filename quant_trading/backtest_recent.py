"""
backtest_recent.py
回測最近 N 筆交易，顯示詳細績效分析。

Usage
─────
    python backtest_recent.py                              # BTC/USDT 4H，最近 30 筆
    python backtest_recent.py --symbol ETH/USDT            # 指定幣種
    python backtest_recent.py --trades 50                  # 最近 50 筆
    python backtest_recent.py --timeframe 1d               # 改用日線
    python backtest_recent.py --symbol BTC/USDT --timeframe 1h --trades 20

注意
────
若 --limit 的 K 棒不足以產生 N 筆交易，請增大 --limit 的值。
例如：python backtest_recent.py --trades 30 --limit 1000
"""

import argparse
import warnings

warnings.filterwarnings("ignore")

import config  # noqa: E402


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="回測最近 N 筆交易績效（v2.0 三層架構）")
    p.add_argument("--symbol",    default=config.SYMBOL,
                   help="交易對，e.g. BTC/USDT（預設來自 config.py）")
    p.add_argument("--timeframe", default=config.TIMEFRAME,
                   help="K 棒週期，e.g. 4h / 1h / 1d（預設來自 config.py）")
    p.add_argument("--limit",     default=config.LIMIT, type=int,
                   help="抓取 K 棒數量（預設 500；不足以產生 N 筆交易時請增加）")
    p.add_argument("--trades",    default=30, type=int,
                   help="顯示最近 N 筆交易（預設 30）")
    return p.parse_args()


def _progress_bar(value: float, width: int = 25) -> str:
    v = max(0.0, min(1.0, value))
    f = int(round(v * width))
    return "█" * f + "░" * (width - f)


def _pnl_pct(direction: str, entry: float, exit_price: float) -> float:
    """Returns trade PnL as a percentage relative to the entry price."""
    if direction == "LONG":
        return (exit_price - entry) / entry * 100
    return (entry - exit_price) / entry * 100


def _max_drawdown_pct(pnl_pcts) -> float:
    """Compute maximum drawdown from a sequence of per-trade PnL percentages."""
    cum = (1 + pnl_pcts / 100).cumprod()
    return float(((cum / cum.cummax()) - 1).min() * 100)


def _streaks(win_flags: list) -> tuple[int, int]:
    """Return (max_consecutive_wins, max_consecutive_losses)."""
    max_cw = max_cl = cw = cl = 0
    for f in win_flags:
        if f:
            cw += 1; cl = 0
        else:
            cl += 1; cw = 0
        max_cw = max(max_cw, cw)
        max_cl = max(max_cl, cl)
    return max_cw, max_cl


def main() -> None:
    args = _parse_args()
    config.SYMBOL    = args.symbol
    config.TIMEFRAME = args.timeframe
    config.LIMIT     = args.limit

    # Late imports so config overrides are applied first
    from data.fetcher               import fetch_ohlcv
    from indicators.ma_ema          import add_ma_ema
    from indicators.rsi             import add_rsi
    from indicators.smc             import add_smc
    from indicators.fvg             import detect_fvg
    from strategy.combined_strategy import generate_signals
    from backtest.engine            import run_backtest

    print("=" * 64)
    print(f"  回測最近 {args.trades} 筆  ·  {args.symbol}  {args.timeframe.upper()}")
    print("=" * 64)

    # ── 1. Data ───────────────────────────────────────────────────────────────
    print("\n[1/3] 抓取 K 棒資料 …")
    df = fetch_ohlcv()
    print(f"      {len(df)} 根  |  {df.index[0]}  →  {df.index[-1]}")

    # ── 2. Indicators ─────────────────────────────────────────────────────────
    print("[2/3] 計算指標 …")
    df = add_ma_ema(df)
    df = add_rsi(df)
    df = add_smc(df)
    df = detect_fvg(df)

    # TF confluence — fetch higher-timeframe trend (Condition D)
    _htf_map = {"15m": "1h", "1h": "4h", "4h": "1d", "1d": "1w"}
    htf_tf   = _htf_map.get(args.timeframe.lower())
    htf_trend = None
    if htf_tf:
        try:
            htf_df    = fetch_ohlcv(args.symbol, htf_tf, limit=250)
            htf_df    = add_ma_ema(htf_df)
            htf_trend = htf_df["trend_up"]
            print(f"      ✓ HTF 趨勢 ({htf_tf.upper()}) 已載入 — 條件 D 啟用")
        except Exception as e:
            print(f"      ⚠ HTF 趨勢取得失敗（{e}）— 條件 D 跳過")

    df = generate_signals(df, htf_trend=htf_trend)
    total_signals = int((df["signal"] != 0).sum())
    print(f"      訊號總數：{total_signals} 個（LONG: {int((df['signal']==1).sum())} / SHORT: {int((df['signal']==-1).sum())}）")

    # ── 3. Backtest ───────────────────────────────────────────────────────────
    print("[3/3] 執行回測引擎 …\n")
    trades_df, metrics, _ = run_backtest(df)

    if "message" in metrics or trades_df.empty:
        print(f"  ⚠  {metrics.get('message', '回測結果為空')}")
        print("     請增加 --limit 或換一個 timeframe，例如：")
        print(f"     python backtest_recent.py --trades {args.trades} --limit 1000")
        return

    n_total = len(trades_df)
    n_show  = min(args.trades, n_total)
    recent  = trades_df.tail(n_show).copy()
    recent["pnl_pct"] = recent.apply(
        lambda r: _pnl_pct(r["direction"], r["entry"], r["exit"]), axis=1
    )

    # ── Performance metrics ───────────────────────────────────────────────────
    n_win      = int((recent["pnl_pct"] > 0).sum())
    n_loss     = n_show - n_win
    win_rate   = n_win / n_show
    gp         = recent.loc[recent["pnl_pct"] > 0, "pnl_pct"].sum()
    gl         = recent.loc[recent["pnl_pct"] < 0, "pnl_pct"].abs().sum()
    pf         = gp / gl if gl > 0 else float("inf")
    total_pnl  = recent["pnl_pct"].sum()
    avg_pnl    = recent["pnl_pct"].mean()
    best_trade = recent["pnl_pct"].max()
    worst_trade = recent["pnl_pct"].min()
    max_dd     = _max_drawdown_pct(recent["pnl_pct"])
    max_cw, max_cl = _streaks((recent["pnl_pct"] > 0).astype(int).tolist())

    # ── Print summary ─────────────────────────────────────────────────────────
    print("=" * 64)
    print(f"  最近 {n_show} 筆  /  全部回測共 {n_total} 筆")
    print("=" * 64)
    print(f"  勝率 Win Rate    : {win_rate:.1%}  {_progress_bar(win_rate)}")
    print(f"  勝 / 敗          : {n_win} / {n_loss}")
    print(f"  利潤因子 PF      : {pf:.2f}")
    print(f"  累計盈虧 PnL     : {total_pnl:+.2f}%")
    print(f"  平均每筆 Avg     : {avg_pnl:+.2f}%")
    print(f"  最佳 Best        : {best_trade:+.2f}%")
    print(f"  最差 Worst       : {worst_trade:+.2f}%")
    print(f"  最大回撤 Max DD  : {max_dd:.2f}%")
    print(f"  最大連勝 / 連敗  : {max_cw} / {max_cl}")

    # ── Direction breakdown ───────────────────────────────────────────────────
    for direction, label in [("LONG", "做多 LONG ▲"), ("SHORT", "做空 SHORT ▼")]:
        sub = recent[recent["direction"] == direction]
        if not sub.empty:
            d_wr = float((sub["pnl_pct"] > 0).mean())
            print(
                f"\n  ── {label}  ({len(sub)} 筆)"
                f"  勝率 {d_wr:.1%}"
                f"  累計 {sub['pnl_pct'].sum():+.2f}%"
                f"  平均 {sub['pnl_pct'].mean():+.2f}%"
            )

    # ── Trade detail table ────────────────────────────────────────────────────
    print(f"\n  {'─'*62}")
    print(f"  {'#':>3}  {'進場時間':^19}  {'方向':^5}  {'進場價':>10}  {'出場價':>10}  {'PnL%':>7}  結果")
    print(f"  {'─'*3}  {'─'*19}  {'─'*5}  {'─'*10}  {'─'*10}  {'─'*7}  ────")
    for i, (_, row) in enumerate(recent.iterrows(), 1):
        marker  = "🎯" if row["result"] in ("TP1", "TP2") else "⚖️" if row["result"] == "BE" else "🛑"
        dir_str = "LONG " if row["direction"] == "LONG" else "SHORT"
        ts      = str(row["entry_time"])[:19]
        print(
            f"  {i:>3}  {ts}  {dir_str}"
            f"  ${row['entry']:>9,.2f}  ${row['exit']:>9,.2f}"
            f"  {row['pnl_pct']:>+7.2f}%  {marker} {row['result']}"
        )
    print(f"  {'─'*62}\n")

    if n_show < args.trades:
        print(
            f"  ⚠  K 棒範圍內只有 {n_total} 筆交易，少於請求的 {args.trades} 筆。\n"
            f"     增加 --limit 可取得更多歷史訊號，例如：\n"
            f"     python backtest_recent.py --trades {args.trades} --limit 1000\n"
        )


if __name__ == "__main__":
    main()
