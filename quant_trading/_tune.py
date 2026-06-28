"""
_tune.py  (temporary tuning harness — safe to delete)
Fetch data once, sweep strategy parameters, report last-N win rate.
"""
import warnings, itertools, importlib
warnings.filterwarnings("ignore")

import config
from data.fetcher import fetch_ohlcv
from indicators.ma_ema import add_ma_ema
from indicators.rsi import add_rsi
from indicators.smc import add_smc
from indicators.fvg import detect_fvg
from backtest.engine import run_backtest

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TF = "4h"
LIMIT = 3000
N = 50

# Cache base data + HTF trend per symbol
base = {}
for sym in SYMBOLS:
    df = fetch_ohlcv(sym, TF, LIMIT)
    df = add_ma_ema(df); df = add_rsi(df); df = add_smc(df); df = detect_fvg(df)
    htf = fetch_ohlcv(sym, "1d", 400)
    htf = add_ma_ema(htf)
    base[sym] = (df, htf["trend_up"])
    print(f"{sym}: {len(df)} bars {df.index[0]} -> {df.index[-1]}")


def evaluate(params, use_htf):
    import strategy.combined_strategy as strat
    importlib.reload(strat)
    rows = []
    for sym in SYMBOLS:
        df, htf = base[sym]
        sig = strat.generate_signals(df, htf_trend=(htf if use_htf else None))
        trades, metrics, _ = run_backtest(sig)
        if trades.empty:
            continue
        t = trades.copy()
        t["pnl_pct"] = t.apply(
            lambda r: (r["exit"]-r["entry"])/r["entry"]*100 if r["direction"]=="LONG"
            else (r["entry"]-r["exit"])/r["entry"]*100, axis=1)
        rows.append((sym, t))
    return rows


def stats(t, n=N):
    recent = t.tail(n)
    wr = (recent["pnl_pct"] > 0).mean()
    gp = recent.loc[recent["pnl_pct"]>0,"pnl_pct"].sum()
    gl = recent.loc[recent["pnl_pct"]<0,"pnl_pct"].abs().sum()
    pf = gp/gl if gl>0 else float("inf")
    return len(recent), wr, pf, recent["pnl_pct"].sum()


# Parameter grid
grid = {
    "RR_RATIO": [1.5],
    "SL_ATR_BUFFER": [0.1, 0.25, 0.5],
    "SL_MIN_ATR": [0.5, 0.8, 1.2],
    "SL_MAX_ATR": [1.5, 2.5, 3.5],
    "RSI_PULLBACK_LONG": [45, 50],
    "RSI_TRIGGER_LONG": [50, 55],
    "RSI_PULLBACK_SHORT": [55, 50],
    "RSI_TRIGGER_SHORT": [50, 45],
    "PULLBACK_LOOKBACK": [4, 6, 10],
}

results = []
keys = list(grid.keys())
combos = list(itertools.product(*[grid[k] for k in keys]))
print(f"Testing {len(combos)} combos x 2 (htf on/off)...")

for use_htf in (False, True):
    for combo in combos:
        for k, v in zip(keys, combo):
            setattr(config, k, v)
        rows = evaluate(combo, use_htf)
        for sym, t in rows:
            n, wr, pf, tot = stats(t)
            results.append((wr, n, pf, tot, sym, use_htf, dict(zip(keys, combo))))

# Filter: enough trades and high WR
good = [r for r in results if r[1] >= 30 and r[0] >= 0.60]
good.sort(key=lambda r: (r[0], r[2]), reverse=True)
print(f"\n{len(good)} configs with >=30 trades and WR>=60%\n")
for wr, n, pf, tot, sym, htf, p in good[:25]:
    print(f"WR={wr:.1%} n={n} PF={pf:.2f} tot={tot:+.1f}% {sym} htf={htf} {p}")
