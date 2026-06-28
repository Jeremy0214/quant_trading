"""
_tune2.py  (temporary tuning harness — safe to delete)
Self-contained parametrized signal generator + sweep. Writes results to file.
"""
import warnings, itertools, json, os, pickle
warnings.filterwarnings("ignore")
import numpy as np, pandas as pd

import config
from data.fetcher import fetch_ohlcv
from indicators.ma_ema import add_ma_ema
from indicators.rsi import add_rsi
from indicators.smc import add_smc
from indicators.fvg import detect_fvg
from backtest.engine import run_backtest

SYMBOLS = ["BTC/USDT", "ETH/USDT"]
TFS = ["4h", "1h"]
LIMIT = 3000
CACHE = "_tune_cache.pkl"


def _atr(df, period=14):
    hl = df["high"] - df["low"]
    hpc = (df["high"] - df["close"].shift()).abs()
    lpc = (df["low"] - df["close"].shift()).abs()
    tr = pd.concat([hl, hpc, lpc], axis=1).max(axis=1)
    return tr.ewm(span=period, adjust=False).mean()


def _rany(s, w):
    return s.astype(int).rolling(w, min_periods=1).max().astype(bool)


def load_data():
    if os.path.exists(CACHE):
        with open(CACHE, "rb") as f:
            return pickle.load(f)
    base = {}
    for tf in TFS:
        for sym in SYMBOLS:
            df = fetch_ohlcv(sym, tf, LIMIT)
            df = add_ma_ema(df); df = add_rsi(df); df = add_smc(df); df = detect_fvg(df)
            htf_tf = {"4h": "1d", "1h": "4h"}[tf]
            htf = fetch_ohlcv(sym, htf_tf, 700)
            htf = add_ma_ema(htf)
            base[(tf, sym)] = (df, htf["trend_up"])
            print(f"{tf} {sym}: {len(df)} bars", flush=True)
    with open(CACHE, "wb") as f:
        pickle.dump(base, f)
    return base


def gen_signals(df, htf_trend, p):
    df = df.copy()
    ema_s = df["EMA_20"]; ema_l = df["EMA_50"]; ema_t = df["EMA_200"]
    rsi = df["RSI"]; atr = _atr(df)
    pb = p["PULLBACK_LOOKBACK"]

    trend_long = (df["close"] > ema_t) & (ema_l > ema_t) & (ema_s > ema_l)
    trend_short = (df["close"] < ema_t) & (ema_l < ema_t) & (ema_s < ema_l)
    if p["USE_HTF"] and htf_trend is not None:
        idx = htf_trend.index.union(df.index)
        ha = htf_trend.reindex(idx).ffill().reindex(df.index)
        trend_long = trend_long & ha.fillna(False).astype(bool)
        trend_short = trend_short & (~ha.fillna(True)).astype(bool)

    touched_l = _rany(df["low"] <= ema_s, pb)
    touched_s = _rany(df["high"] >= ema_s, pb)
    reset_l = _rany(rsi < p["RSI_PULLBACK_LONG"], pb)
    reset_s = _rany(rsi > p["RSI_PULLBACK_SHORT"], pb)
    cross_up = (rsi > p["RSI_TRIGGER_LONG"]) & (rsi.shift(1) <= p["RSI_TRIGGER_LONG"])
    cross_dn = (rsi < p["RSI_TRIGGER_SHORT"]) & (rsi.shift(1) >= p["RSI_TRIGGER_SHORT"])
    reclaim_l = (df["close"] > df["open"]) & (df["close"] > ema_s)
    reclaim_s = (df["close"] < df["open"]) & (df["close"] < ema_s)
    hot_l = rsi < p["RSI_MAX_LONG"]
    hot_s = rsi > p["RSI_MIN_SHORT"]

    long_mask = trend_long & touched_l & reset_l & cross_up & reclaim_l & hot_l
    short_mask = trend_short & touched_s & reset_s & cross_dn & reclaim_s & hot_s

    sw_lo = df["low"].rolling(p["SL_SWING_LOOKBACK"], min_periods=1).min()
    sw_hi = df["high"].rolling(p["SL_SWING_LOOKBACK"], min_periods=1).max()
    entry = df["close"]
    dl = (entry - (sw_lo - atr * p["SL_ATR_BUFFER"])).clip(
        lower=atr * p["SL_MIN_ATR"], upper=atr * p["SL_MAX_ATR"])
    ds = ((sw_hi + atr * p["SL_ATR_BUFFER"]) - entry).clip(
        lower=atr * p["SL_MIN_ATR"], upper=atr * p["SL_MAX_ATR"])

    df["signal"] = 0
    df["sl_price"] = np.nan; df["tp_price"] = np.nan
    df.loc[long_mask, "signal"] = 1
    df.loc[short_mask, "signal"] = -1
    df.loc[long_mask, "sl_price"] = (entry - dl)[long_mask]
    df.loc[long_mask, "tp_price"] = (entry + dl * p["RR_RATIO"])[long_mask]
    df.loc[short_mask, "sl_price"] = (entry + ds)[short_mask]
    df.loc[short_mask, "tp_price"] = (entry - ds * p["RR_RATIO"])[short_mask]
    return df


def trades_for(df, htf, p):
    sig = gen_signals(df, htf, p)
    trades, _, _ = run_backtest(sig)
    if trades.empty:
        return pd.DataFrame()
    t = trades.copy()
    t["pnl_pct"] = t.apply(
        lambda r: (r["exit"] - r["entry"]) / r["entry"] * 100 if r["direction"] == "LONG"
        else (r["entry"] - r["exit"]) / r["entry"] * 100, axis=1)
    return t


def wr_stats(t, n=50):
    r = t.tail(n)
    if len(r) == 0:
        return 0, 0.0, 0.0
    wr = (r["pnl_pct"] > 0).mean()
    gp = r.loc[r["pnl_pct"] > 0, "pnl_pct"].sum()
    gl = r.loc[r["pnl_pct"] < 0, "pnl_pct"].abs().sum()
    pf = gp / gl if gl > 0 else 99.0
    return len(r), wr, pf


base = load_data()

grid = {
    "RR_RATIO": [1.5],
    "SL_ATR_BUFFER": [0.15, 0.4],
    "SL_MIN_ATR": [0.6, 1.0],
    "SL_MAX_ATR": [2.0, 3.0],
    "RSI_PULLBACK_LONG": [45, 50],
    "RSI_TRIGGER_LONG": [50, 55],
    "RSI_PULLBACK_SHORT": [55, 50],
    "RSI_TRIGGER_SHORT": [50, 45],
    "RSI_MAX_LONG": [70],
    "RSI_MIN_SHORT": [30],
    "PULLBACK_LOOKBACK": [4, 6, 10],
    "SL_SWING_LOOKBACK": [8, 12],
    "USE_HTF": [True, False],
}
keys = list(grid.keys())
combos = list(itertools.product(*[grid[k] for k in keys]))
print(f"Testing {len(combos)} combos across {len(TFS)} timeframes", flush=True)

out = []
for tf in TFS:
    for combo in combos:
        p = dict(zip(keys, combo))
        all_t = []
        per = {}
        for sym in SYMBOLS:
            df, htf = base[(tf, sym)]
            t = trades_for(df, htf, p)
            per[sym] = t
            if not t.empty:
                all_t.append(t)
        if not all_t:
            continue
        comb = pd.concat(all_t).sort_values("entry_time")
        cn, cwr, cpf = wr_stats(comb, 50)
        c50_n, c50_wr, c50_pf = wr_stats(comb, 10**9)  # all combined trades
        bsym = {s: wr_stats(per[s], 30) for s in SYMBOLS if not per[s].empty}
        out.append({"tf": tf, "comb_last50_n": int(cn), "comb_last50_wr": round(cwr, 3),
                    "comb_last50_pf": round(cpf, 2),
                    "comb_all_n": int(c50_n), "comb_all_wr": round(c50_wr, 3),
                    "per30": {s: [v[0], round(v[1], 3), round(v[2], 2)] for s, v in bsym.items()},
                    "p": p})

# Frontier A: best last-50 WR among configs with >=50 combined trades
A = [r for r in out if r["comb_last50_n"] >= 50]
A.sort(key=lambda r: (r["comb_last50_wr"], r["comb_last50_pf"]), reverse=True)
# Frontier B: best last-50 WR among configs with >=40 combined trades
B = [r for r in out if r["comb_last50_n"] >= 40]
B.sort(key=lambda r: (r["comb_last50_wr"], r["comb_last50_pf"]), reverse=True)
# Frontier C: best overall WR (all trades), require >=30 trades
C = [r for r in out if r["comb_all_n"] >= 30]
C.sort(key=lambda r: (r["comb_all_wr"], r["comb_last50_pf"]), reverse=True)

with open("_tune_results.txt", "w", encoding="utf-8") as f:
    f.write("=== A: >=50 combined trades, sorted by last-50 WR ===\n")
    for r in A[:15]:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.write("\n=== B: >=40 combined trades, sorted by last-50 WR ===\n")
    for r in B[:15]:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
    f.write("\n=== C: >=30 combined trades, sorted by all-trades WR ===\n")
    for r in C[:15]:
        f.write(json.dumps(r, ensure_ascii=False) + "\n")
print(f"Done. total={len(out)}  A(>=50)={len(A)}  B(>=40)={len(B)}  C(>=30)={len(C)}", flush=True)
for lbl, lst in (("A", A), ("B", B), ("C", C)):
    print(f"-- top {lbl} --", flush=True)
    for r in lst[:5]:
        print(lbl, r["tf"], "last50:", r["comb_last50_n"], r["comb_last50_wr"], r["comb_last50_pf"],
              "all:", r["comb_all_n"], r["comb_all_wr"], flush=True)
