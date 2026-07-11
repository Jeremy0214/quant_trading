from analyzer import analyze_stocks
from config import SETTINGS

test_stocks = {
    "AAPL": "蘋果",
    "NVDA": "輝達",
    "TSLA": "特斯拉",
    "2330.TW": "台積電",
    "2317.TW": "鴻海",
}
settings = {**SETTINGS, "min_score": 0}
results = analyze_stocks(test_stocks, market="TEST", settings=settings)
for r in results:
    print(f"{r['name']}({r['ticker']}) 評分:{r['score']}/12 信號:{r['signals']}")
print("分析引擎測試完成 ✅")
