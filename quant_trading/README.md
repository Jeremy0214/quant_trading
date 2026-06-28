# SMC + FVG + EMA + RSI 量化交易策略

一個基於 **Smart Money Concepts (SMC)**、**Fair Value Gap (FVG)**、**EMA 均線**與 **RSI** 的加密貨幣量化交易系統，支援：
- 多幣種即時訊號監控（Binance 4H）
- Discord 進場/止盈/止損通知（含點位）
- 自動回測與績效評估
- 持倉追蹤與勝率統計日誌

---

## 目錄

- [策略邏輯](#策略邏輯)
- [專案結構](#專案結構)
- [安裝](#安裝)
- [設定](#設定)
- [使用方式](#使用方式)
- [Discord 通知範例](#discord-通知範例)
- [回測結果](#回測結果)
- [指令速查](#指令速查)

---

## 策略邏輯

### 指標說明

| 指標 | 說明 |
|---|---|
| **EMA 20 / 50 / 200** | 短中長期趨勢，EMA20/50 方向為第一層必要條件 |
| **RSI (14)** | 趨勢延續（>55 多方 / <45 空方）或回調反彈（<40 後穿越 45 / >60 後穿越 55 做空）判斷動能 |
| **SMC — Swing High/Low** | 識別市場結構的樞紐高低點 |
| **SMC — BOS** (Break of Structure) | 收盤突破前高/前低，確認結構方向 |
| **SMC — CHoCH** (Change of Character) | 第一個反向 BOS，代表趨勢可能轉折 |
| **SMC — Order Block** | BOS 前最後一根反向K棒，作為機構掛單區與止損錨點 |
| **FVG** (Fair Value Gap) | 三K棒價格缺口，與 OB 共同構成 SMC 結構確認 |
| **ATR (14)** | 波動率過濾（條件 E，ATR > 均值 × 90%）與止損距離驗證（第三層）|

---

### 三層篩選架構（v2.0）

```
第一層：硬性前提（2 項全數成立）
    ↓ 通過才進入第二層
第二層：訊號評分（5 選 3）
    ↓ 通過才進入第三層
第三層：風險管理驗證（2 項全數成立）
    ↓ 通過 → 輸出訊號
```

### 第一層：硬性前提

> 任一不成立 → 直接放棄此訊號

| 方向 | 條件 1 | 條件 2 |
|:---:|---|---|
| 🟢 做多 LONG | 收盤 **>** EMA 200 | EMA 20 **>** EMA 50 |
| 🔴 做空 SHORT | 收盤 **<** EMA 200 | EMA 20 **<** EMA 50 |

### 第二層：訊號評分（5 項，需 ≥ 3 項）

| 條件 | 做多判斷 | 做空判斷 |
|---|---|---|
| **A 動能** | RSI > 55，或 RSI 從 <40 回升穿越 45 | RSI < 45，或 RSI 從 >60 下穿 55 |
| **B SMC 結構** | 近 10 根 K 棒看漲 BOS + (OB 或未填 FVG) — 整組 **1 票** | 近 10 根 K 棒看跌 BOS + (OB 或未填 FVG) — 整組 **1 票** |
| **C K 棒品質** | 實體比 > 65% 且收盤於 K 棒頂部 30% 區 | 實體比 > 65% 且收盤於 K 棒底部 30% 區 |
| **D TF 共振** | 高一級 TF 的 EMA200 趨勢向上 | 高一級 TF 的 EMA200 趨勢向下 |
| **E 波動性** | ATR(14) > 近 20 根 ATR 均值 × 90% | 同左 |

> TF 對照：15m ↑ 1H、1H ↑ 4H、4H ↑ 日線、日線 ↑ 週線

### 第三層：風險管理

> 任一不成立 → 等待更好的入場點

| 驗證 | 標準 |
|---|---|
| **SL 錨點明確** | 近期 OB 低點 / FVG 底部存在（作為止損基準）|
| **SL 距離合理** | \|進場價 − SL\| ≤ ATR(14) × 1.5 |

> R:R 驗證：止盈設為 SL 距離 × 2.0 → R:R = 1:2 ≥ 1:1.5 ✓

### 止盈止損（預設）

| 參數 | 預設 |
|---|---|
| 止損 Stop Loss | 進場價 ± ATR × 2.0 |
| 止盈 Take Profit | 進場價 ± ATR × 4.0 |
| 風報比 R:R | 1 : 2.0 |

---

## 專案結構

```
quant_trading/
│
├── config.py                    # 所有可調整參數
├── main.py                      # 一次性分析 + 圖表
├── monitor.py                   # 即時監控主程式
├── stats.py                     # 即時績效查詢工具
├── backtest_recent.py           # 最近 N 筆交易回測分析
├── requirements.txt
│
├── data/
│   └── fetcher.py               # Binance OHLCV 資料抓取 (ccxt)
│
├── indicators/
│   ├── ma_ema.py                # SMA / EMA 計算
│   ├── rsi.py                   # RSI 計算
│   ├── smc.py                   # Swing、BOS、CHoCH、Order Block
│   └── fvg.py                   # FVG 偵測與填補狀態
│
├── strategy/
│   └── combined_strategy.py     # 訊號評分邏輯（6 條件）
│
├── backtest/
│   └── engine.py                # 事件驅動回測引擎
│
├── tracker/
│   └── trade_tracker.py         # 即時交易日誌（trades_log.json）
│
├── alerts/
│   └── discord.py               # Discord Webhook 進場/出場通知
│
└── visualization/
    └── chart.py                 # Plotly 互動式 HTML 圖表
```

---

## 安裝

**需求：Python 3.10+**

```bash
# 1. 進入專案資料夾
cd quant_trading

# 2. 安裝套件
pip install -r requirements.txt
```

---

## 設定

開啟 `config.py`，根據需求調整：

```python
# 監控幣種（可新增任意 Binance 交易對）
MONITOR_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
MONITOR_TIMEFRAME = "4h"

# 輪詢間隔（秒），預設 5 分鐘
CHECK_INTERVAL_SECONDS = 300

# Discord Webhook URL（必填才能收通知）
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/..."

# 止盈止損 ATR 倍數
STOP_LOSS_ATR_MULT   = 2.0
TAKE_PROFIT_ATR_MULT = 4.0   # 風報比 1:2
```

### 取得 Discord Webhook URL

1. 開啟 Discord → 目標頻道 → ⚙️ 設定
2. **整合 Integrations** → **Webhooks** → **建立 Webhook**
3. 複製 URL，貼入 `config.py`

> ⚠️ **請勿將 Webhook URL 上傳至 Git 或公開分享**

---

## 使用方式

### 1. 單次分析 + 圖表

對指定幣種跑完整指標計算、回測，並輸出互動式圖表（`chart.html`）：

```bash
# 預設 BTC/USDT 4H
python main.py

# 自訂幣種與週期
python main.py --symbol ETH/USDT --timeframe 1h --limit 500

# 不自動開啟瀏覽器
python main.py --no-browser
```

### 2. 即時監控

持續輪詢 Binance，偵測到新訊號時自動發送 Discord 通知：

```bash
python monitor.py
```

- 每 **5 分鐘** 掃描一次 BTC/USDT 與 ETH/USDT
- **只評估最後一根已收盤的 K 棒**（排除當前未收盤的 live 蠟燭，避免指標值抖動誤觸發）
- 同一根 K 棒的訊號**只通知一次**（以 K 棒開盤時間戳去重，每根 4H K 棒最多一次通知）
- 偵測到止盈/止損觸發時，自動發送出場通知
- 每小時在 log 中印出即時績效摘要
- 所有事件記錄至 `monitor.log`

停止監控：`Ctrl + C`

### 3. 查看即時績效

```bash
# 勝率摘要
python stats.py

# 所有交易明細
python stats.py --trades

# 只看未出場的持倉
python stats.py --open
```

### 4. 回測最近 N 筆交易

對歷史 K 棒執行完整指標 + 訊號 + 回測，並聚焦顯示最近 N 筆的詳細績效：

```bash
# 預設：BTC/USDT 4H，最近 30 筆
python backtest_recent.py

# 指定幣種與週期
python backtest_recent.py --symbol ETH/USDT --timeframe 1h

# 自訂筆數
python backtest_recent.py --trades 50

# 增加 K 棒數量以確保有足夠交易紀錄
python backtest_recent.py --trades 30 --limit 1000
```

輸出包含：勝率、利潤因子、累計盈虧、最大回撤、最大連勝/連敗、LONG/SHORT 分析、逐筆交易明細。

---

## Discord 通知範例

### 進場訊號
```
🟢 做多 ▲ — BTC/USDT 4H
💰 進場價格    : $64,509.40
🛑 止損點位    : $62,761.52  (-2.71%)
🎯 止盈點位    : $68,005.16  (+5.42%)
⚖️ 風報比      : 1 : 2.0
📊 RSI（14）   : 44.8
⭐ 訊號強度    : 4 / 5
📉 主趨勢      : 上升趨勢（收盤高於 EMA 200）
〰️ 短期動能    : EMA 20 > EMA 50（短期動能向上 ↑）
🏛️ 市場結構突破（BOS）: ✅ 確認
🧱 機構掛單區（OB）   : ✅ 確認
⚡ 失衡缺口（FVG）    : ✅ 未填補看漲缺口
```

### 止盈觸發
```
🎯 TAKE PROFIT HIT — BTC/USDT 4H
🎯 止盈觸發 — BTC/USDT 4H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $68,005.16   📈 盈虧: ✅ +5.42%
⚖️ 風報比: 1 : 2.0   🔖 交易編號: a1b2c3d4
```

### 止損觸發
```
🛑 止損觸發 — BTC/USDT 4H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $62,761.52   📈 盈虧: ❌ -2.71%
```

---

## 回測結果

測試期間：**2026-01-03 ~ 2026-06-19**（1000 根 4H K棒，約 5.5 個月）

### BTC/USDT 4H

| 風報比 | 交易次數 | 勝率 | 利潤因子 | 總報酬 | 最大回撤 |
|---|---|---|---|---|---|
| 1 : 1.5 | 48 | 50.0% | 1.47 | +25.2% | 14.1% |
| 1 : 2.0 | 28 | 50.0% | 1.97 | +30.5% | 11.5% |
| **1 : 3.0** | **15** | **53.3%** | **3.33** | **+38.4%** | **5.9%** |

### ETH/USDT 4H

| 風報比 | 交易次數 | 勝率 | 利潤因子 | 總報酬 | 最大回撤 |
|---|---|---|---|---|---|
| **1 : 1.5** | **43** | **53.5%** | **1.68** | **+31.8%** | **9.9%** |
| 1 : 2.0 | 23 | 47.8% | 1.77 | +20.8% | 9.8% |
| 1 : 3.0 | 16 | 37.5% | 1.75 | +15.9% | 9.6% |

> 預設設定（`SL=2.0×ATR, TP=4.0×ATR`）為兩個幣種的平衡選擇。

---

## 指令速查

| 目的 | 指令 |
|---|---|
| 單次分析 + 圖表 | `python main.py` |
| 指定幣種分析 | `python main.py --symbol ETH/USDT --timeframe 1h` |
| 啟動即時監控 | `python monitor.py` |
| 查看勝率摘要 | `python stats.py` |
| 查看交易明細 | `python stats.py --trades` |
| 查看持倉中訂單 | `python stats.py --open` |
| 回測最近 30 筆 | `python backtest_recent.py` |
| 回測最近 N 筆（自訂） | `python backtest_recent.py --trades 50 --symbol ETH/USDT` |
| 回測（增加 K 棒） | `python backtest_recent.py --trades 30 --limit 1000` |

---

## 注意事項

- 本程式使用 **收盤價** 作為進場點，正式使用建議改為下一根 K 棒開盤價入場
- 回測結果為歷史績效，**不代表未來獲利保證**
- 請務必搭配自身資金管理策略使用
- 預設每筆交易風險為帳戶淨值的 **2%**（可在 `config.py` 調整 `RISK_PER_TRADE`）
