"""
stats.py
隨時執行，顯示 trades_log.json 的即時勝率與損益摘要。

Usage
─────
    python stats.py           # 顯示摘要
    python stats.py --trades  # 顯示所有交易明細
    python stats.py --open    # 只顯示還未出場的倉位
"""

import argparse
import json
from pathlib import Path

from tracker.trade_tracker import get_summary, get_open_trades, get_all_trades

TRADES_FILE = Path("trades_log.json")


def _bar(value: float, width: int = 30, char: str = "█") -> str:
    filled = int(round(value * width))
    return char * filled + "░" * (width - filled)


def print_summary() -> None:
    s = get_summary()

    print("\n" + "=" * 58)
    print("  即時交易績效  Live Trade Performance")
    print("=" * 58)

    if "message" in s:
        print(f"  {s['message']}")
        open_trades = get_open_trades()
        if open_trades:
            print(f"\n  未出場倉位 Open: {len(open_trades)}")
        print("=" * 58)
        return

    wr = s["win_rate"]
    print(f"  已結算 Closed  : {s['total_closed']}  (勝 {s['wins']} / 敗 {s['losses']})")
    print(f"  持倉中 Open    : {s['open_trades']}")
    print(f"  勝率 Win Rate  : {wr:.1%}  {_bar(wr)}")
    print(f"  利潤因子 PF    : {s['profit_factor']:.2f}")
    print(f"  累計盈虧 PnL   : {s['total_pnl_pct']:+.2f}%")
    print(f"  平均盈虧 Avg   : {s['avg_pnl_pct']:+.2f}%")
    print(f"  最佳 Best      : {s['best_trade_pct']:+.2f}%")
    print(f"  最差 Worst     : {s['worst_trade_pct']:+.2f}%")

    print(f"\n  ── 各幣種分析 By Symbol {'─'*32}")
    for sym, d in s.get("by_symbol", {}).items():
        print(
            f"  {sym:<12}  交易={d['trades']}  勝率={d['win_rate']:.1%}"
            f"  累計={d['total_pnl_pct']:+.2f}%"
        )
    print("=" * 58)


def print_trades(trades: list, title: str) -> None:
    print(f"\n{'─'*80}")
    print(f"  {title}  ({len(trades)} 筆)")
    print(f"{'─'*80}")
    if not trades:
        print("  (無資料)")
        return

    hdr = f"  {'ID':^8}  {'Symbol':^10}  {'Dir':^6}  {'Entry':>10}  {'SL':>10}  {'TP':>10}  {'Exit':>10}  {'PnL':>8}  {'Result':^6}"
    print(hdr)
    print(f"  {'─'*8}  {'─'*10}  {'─'*6}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*10}  {'─'*8}  {'─'*6}")

    for t in trades:
        exit_p  = f"${t['exit_price']:,.2f}" if t["exit_price"] else "——"
        pnl_str = f"{t['pnl_pct']:+.2f}%" if t["pnl_pct"] is not None else "——"
        result  = t["result"]
        marker  = "🎯" if result == "TP" else "🛑" if result == "SL" else "⏳"
        print(
            f"  {t['id']:^8}  {t['symbol']:^10}  {t['direction']:^6}"
            f"  ${t['entry_price']:>9,.2f}"
            f"  ${t['stop_loss']:>9,.2f}"
            f"  ${t['take_profit']:>9,.2f}"
            f"  {exit_p:>10}"
            f"  {pnl_str:>8}"
            f"  {marker} {result}"
        )
    print(f"{'─'*80}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Live trade journal viewer")
    parser.add_argument("--trades", action="store_true", help="Show all trade details")
    parser.add_argument("--open",   action="store_true", help="Show only open positions")
    args = parser.parse_args()

    if not TRADES_FILE.exists():
        print("\n  trades_log.json 尚不存在，請先啟動 monitor.py 並等待第一個訊號。")
        return

    if args.open:
        print_trades(get_open_trades(), "未出場倉位 Open Positions")
    elif args.trades:
        print_trades(get_all_trades(), "所有交易明細 All Trades")
    else:
        print_summary()
        # Also show open positions
        open_t = get_open_trades()
        if open_t:
            print_trades(open_t, "⏳ 持倉中 Open Positions")


if __name__ == "__main__":
    main()
