# 📊 股票投顧機器人

自動分析台股與美股熱門股票，每日透過 **Discord Webhook** 傳送技術分析推薦，幫助你掌握買入時機。

---

## ✨ 功能特色

- 🇹🇼 **台股 Top 50** + 🇺🇸 **美股 Top 50** 同步分析
- 6 項技術指標綜合評分，最高 12 分
- Discord 美觀 Embed 格式，包含價格、漲跌幅、技術信號
- 可自訂股票清單、排程時間、評分門檻
- 每日定時自動執行，無需手動操作

---

## 📁 專案結構

```
stock_buy/
├── main.py              # 主程式，立即執行一次分析
├── scheduler.py         # 每日定時排程執行器
├── analyzer.py          # 技術分析引擎
├── discord_notifier.py  # Discord Webhook 傳送模組
├── config.py            # 股票清單與分析參數設定
├── webhook.txt          # Discord Webhook URL (勿上傳 Git)
├── .env                 # 排程時間等環境變數設定
├── .env.example         # .env 範本
├── requirements.txt     # Python 套件清單
└── .gitignore
```

---

## 🚀 快速開始

### 1. 安裝套件

```bash
pip install -r requirements.txt
```

### 2. 設定 Discord Webhook URL

在 `webhook.txt` 中貼上你的 Discord Webhook URL（只需第一行）：

```
https://discord.com/api/webhooks/1234567890/abcdefghij...
```

> **如何取得 Webhook URL？**
> Discord 伺服器 → 頻道設定 → 整合 → Webhooks → 建立 Webhook → 複製 URL

### 3. 設定排程時間（選填）

複製 `.env.example` 為 `.env`，可調整以下參數：

```env
SCHEDULE_TIME=09:00   # 每日執行時間（本機時間）
MIN_SCORE=5           # 最低推薦評分門檻（0-12）
```

### 4. 執行

**立即執行一次：**
```bash
python main.py
```

**每日定時自動執行：**
```bash
python scheduler.py
```

---

## 📊 評分系統

共 6 項技術指標，每項最高 2 分，**總分 12 分**：

| # | 指標 | 觸發條件 | 分數 |
|---|------|---------|------|
| 1 | **RSI 相對強弱指標** | RSI < 30（超賣） | 2 分 |
|   |                     | RSI < 40（偏低） | 1 分 |
| 2 | **MACD** | 黃金交叉（MACD 向上穿越訊號線） | 2 分 |
|   |          | MACD 在訊號線上方 | 1 分 |
| 3 | **均線排列** | 收盤 > MA20 且 MA20 > MA60（多頭排列） | 2 分 |
|   |             | 收盤 > MA20 | 1 分 |
| 4 | **成交量** | 當日量 ≥ 1.5 倍 20 日均量（爆量） | 2 分 |
|   |            | 當日量 ≥ 1.2 倍 20 日均量（量增） | 1 分 |
| 5 | **KD 隨機指標** | K < 20 且 K 向上穿越 D（超賣交叉） | 2 分 |
|   |                | K < 30（超賣區間） | 1 分 |
| 6 | **布林通道** | 收盤跌破布林下軌 | 2 分 |
|   |              | 收盤在布林帶下四分之一區間 | 1 分 |

### 推薦等級

| 分數 | 等級 |
|------|------|
| 🔥 10–12 | 強力買入 |
| 📈 7–9   | 建議買入 |
| 👀 5–6   | 值得關注 |

> 預設只顯示評分 ≥ 5 的股票，可在 `.env` 中調整 `MIN_SCORE`。

---

## 💬 Discord 訊息範例

```
📢 每日股票投顧報告來了！

📊 每日股票投顧推薦
📅 日期：2026 年 07 月 11 日（週六）
🇹🇼 台股推薦：3 檔
🇺🇸 美股推薦：5 檔

🇹🇼 台股推薦
━━━━━━━━━━━━━━━━━━━━━━━━
#1 鴻海（2317.TW）
   💰 NT$ 185.50  🟢 +2.21%
   🎯 評分：8/12  📈 建議買入
   📊 KD超賣交叉(K=18.3) ｜ 爆量(1.8x) ｜ MACD黃金交叉
```

---

## ⚙️ 自訂股票清單

修改 `config.py` 中的 `TW_STOCKS` 或 `US_STOCKS`：

```python
# 台股格式：股票代號.TW
TW_STOCKS = {
    "2330.TW": "台積電",
    "6547.TW": "高端疫苗",   # 新增
}

# 美股格式：直接填 Ticker
US_STOCKS = {
    "AAPL": "蘋果",
    "PLTR": "Palantir",
}
```

---

## 🔧 測試分析引擎

不需要 Discord Webhook 也能測試分析功能：

```bash
python test_analyzer.py
```

---

## ⚠️ 免責聲明

本程式依據公開技術指標自動產生推薦，**僅供參考，不構成任何投資建議**。股票投資存在風險，請在充分了解風險後自行判斷操作，本程式作者不對任何投資損失負責。

---

## 📦 使用套件

| 套件 | 用途 |
|------|------|
| [yfinance](https://github.com/ranaroussi/yfinance) | 抓取股票歷史資料 |
| [ta](https://github.com/bukosabino/ta) | 技術分析指標計算 |
| [pandas](https://pandas.pydata.org/) | 資料處理 |
| [requests](https://requests.readthedocs.io/) | Discord Webhook 傳送 |
| [schedule](https://schedule.readthedocs.io/) | 定時排程 |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | 環境變數管理 |
