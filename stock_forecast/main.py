"""
main.py ── 台股個股評估與買賣訊號預測系統
執行方式：
    python main.py              (互動式輸入)
    python main.py 2330         (直接帶入股號)
    python main.py 2330 6505    (批次分析多支)
"""

from __future__ import annotations

import sys

from colorama import Fore, Style, init as colorama_init

from modules.data_fetcher import StockDataFetcher
from modules.fundamental_analyzer import FundamentalAnalyzer
from modules.institutional_analyzer import InstitutionalAnalyzer
from modules.price_target import PriceTargetCalculator
from modules.report_generator import ReportGenerator
from modules.technical_analyzer import TechnicalAnalyzer

colorama_init(autoreset=True)


def analyze(ticker_id: str) -> None:
    """執行單一股票完整分析並輸出報告。"""
    print(
        Fore.CYAN
        + f"\n⏳ 正在分析股票代號：{ticker_id}，請稍候..."
        + Style.RESET_ALL
    )

    # 1. 抓取資料
    try:
        fetcher = StockDataFetcher(ticker_id).fetch_all()
    except ValueError as exc:
        print(Fore.RED + f"  {exc}" + Style.RESET_ALL)
        return

    # 2. 分析
    fund_result  = FundamentalAnalyzer(fetcher).analyze()
    tech_result  = TechnicalAnalyzer(fetcher).analyze()
    insti_result = InstitutionalAnalyzer(fetcher).analyze()
    price_target = PriceTargetCalculator(fetcher, fund_result, tech_result).calculate()

    # 3. 輸出報告
    ReportGenerator(fetcher, fund_result, tech_result, price_target, insti_result).print_report()


def main() -> None:
    tickers = sys.argv[1:]

    if not tickers:
        raw = input(
            Fore.YELLOW
            + "請輸入台股代號（可輸入多個，以空格分隔，例如：2330 6505）：\n> "
            + Style.RESET_ALL
        ).strip()
        tickers = raw.split() if raw else []

    if not tickers:
        print(Fore.RED + "❌ 未輸入任何股票代號，程式結束。" + Style.RESET_ALL)
        sys.exit(1)

    for tid in tickers:
        analyze(tid)


if __name__ == "__main__":
    main()
