# Jeremy 的交易系統與分析工具

本專案包含兩個量化交易與股票分析系統：

---

## 📊 1. quant_trading - 加密貨幣量化交易策略

**概述：** 一個基於 **Smart Money Concepts (SMC)**、**Fair Value Gap (FVG)**、**EMA 均線**與 **RSI** 的加密貨幣量化交易系統。

### 主要功能
- ✅ **多幣種即時訊號監控** - Binance 4H 時框
- ✅ **Discord 進場/止盈/止損通知** - 包含詳細點位
- ✅ **自動回測與績效評估** - 歷史策略驗證
- ✅ **持倉追蹤與勝率統計日誌** - 實時績效監控

### 核心指標
| 指標 | 說明 |
|---|---|
| **EMA 20/50/200** | 短中長期趨勢判斷 |
| **RSI (14)** | 動能與回調反彈確認 |
| **SMC** | Swing High/Low、BOS、CHoCH、Order Block |
| **FVG** | 三K棒價格缺口 |
| **ATR (14)** | 波動率過濾與止損距離驗證 |

### 三層篩選架構
```
第一層：硬性前提 (2 項全數成立) → 進入第二層
第二層：訊號評分 (5 選 3) → 進入第三層
第三層：風險管理驗證 (2 項全數成立) → 輸出訊號
```

### 技術棧
- 資料來源：CCXT、Binance API
- 依賴套件：pandas, numpy, plotly, requests

---

## 📈 2. stock_forecast - 台股個股評估與買賣訊號預測系統

**概述：** 接收台灣股票代號，自動抓取財務與歷史股價資料，計算基本面與技術面指標，輸出含「買賣建議」與「信心指數」的評估報告。

### 主要功能
- ✅ **財務資料抓取** - 使用 yfinance 與 MOPS 資料
- ✅ **基本面評分** - 獲利性、成長性、財務安全性
- ✅ **技術面評分** - 趨勢、動能、支撐阻力
- ✅ **買賣訊號預測** - 結合信心指數的投資建議
- ✅ **批次分析** - 一次評估多支股票

### 使用方式
```bash
# 分析單支股票
python main.py 2330

# 批次分析多支股票
python main.py 2330 2412 6505

# 互動模式
python main.py
```

### 技術棧
- 資料來源：yfinance、MOPS
- 依賴套件：pandas, numpy, requests, lxml, html5lib, discord.py, python-dotenv

---

## 📁 專案結構

```
├── quant_trading/               # 加密貨幣量化交易系統
│   ├── main.py                  # 主程式入口
│   ├── monitor.py               # 即時監控模組
│   ├── config.py                # 策略參數配置
│   ├── requirements.txt
│   ├── alerts/                  # Discord 通知模組
│   ├── backtest/                # 回測引擎
│   ├── data/                    # 資料抓取模組
│   ├── indicators/              # 技術指標計算 (SMC, FVG, EMA, RSI)
│   ├── strategy/                # 交易策略組合
│   ├── tracker/                 # 交易追蹤與統計
│   └── visualization/           # 圖表生成
│
└── stock_forecast/              # 台股評估系統
    ├── main.py                  # 主程式入口
    ├── config.py                # 評分參數配置
    ├── requirements.txt
    ├── modules/
    │   ├── data_fetcher.py      # 資料抓取模組
    │   ├── fundamental_analyzer.py  # 基本面分析
    │   ├── technical_analyzer.py    # 技術面分析
    │   ├── institutional_analyzer.py
    │   ├── price_target.py
    │   └── report_generator.py  # 報告生成
```

---

## 🚀 快速開始

### quant_trading
```bash
cd quant_trading
pip install -r requirements.txt
python main.py
```
```
VM Look & Edit

Look:
tmux attach

Edit： nano 檔案名稱 (例如：nano config.txt)

操作方式：
使用鍵盤方向鍵移動游標並直接修改文字。
修改完成後，按下 Ctrl + O 準備存檔，接著按 Enter 確認檔名。
按下 Ctrl + X 離開編輯器。
```
### stock_forecast
```bash
cd stock_forecast
pip install -r requirements.txt
python main.py 2330
```

---

## 📝 注意事項

- 兩個系統各自獨立運行，擁有獨立的依賴與配置
- 建議在虛擬環境中分別安裝依賴
- 加密貨幣系統需要 Discord 機器人 Token 與 Binance API 密鑰
- 台股系統需要網路連接以抓取即時資料
