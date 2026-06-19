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
| **EMA 20 / 50 / 200** | 短中長期趨勢判斷，EMA 20/50 交叉為動能訊號 |
| **RSI (14)** | 超買 >70 / 超賣 <30，策略取中間範圍作為入場過濾 |
| **SMC — Swing High/Low** | 識別市場結構的樞紐高低點 |
| **SMC — BOS** (Break of Structure) | 收盤價突破前高/前低，代表市場結構改變 |
| **SMC — CHoCH** (Change of Character) | 第一個反向 BOS，代表趨勢可能轉折 |
| **SMC — Order Block** | BOS 前最後一根反向K棒，代表機構掛單區 |
| **FVG** (Fair Value Gap) | 三根K棒形成的價格缺口（失衡區），價格傾向回補 |

### 訊號條件（6 項，需滿足 ≥ 4 項）

**做多 LONG**
1. 收盤價在 EMA 200 之上（主趨勢向上）
2. EMA 20 > EMA 50（短期動能向上）
3. RSI 介於 30 ~ 55（非超買，微回調）
4. 近期出現看漲 Order Block
5. 存在未填補的看漲 FVG
6. 近期出現看漲 BOS

**做空 SHORT**（以上條件鏡像）

### 止盈止損

| 參數 | 預設 |
|---|---|
| 止損 Stop Loss | 進場價 − ATR × 2.0 |
| 止盈 Take Profit | 進場價 + ATR × 4.0 |
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
- 同一根 K 棒的訊號**只通知一次**（重複偵測自動略過）
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
⭐ 訊號強度    : 4 / 6
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

---

## 注意事項

- 本程式使用 **收盤價** 作為進場點，正式使用建議改為下一根 K 棒開盤價入場
- 回測結果為歷史績效，**不代表未來獲利保證**
- 請務必搭配自身資金管理策略使用
- 預設每筆交易風險為帳戶淨值的 **2%**（可在 `config.py` 調整 `RISK_PER_TRADE`）
