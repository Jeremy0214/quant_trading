# 量化交易策略監控系統

一個針對 **BTC/USDT、ETH/USDT** 的加密貨幣量化交易系統，基於「**品質趨勢回調**」策略（v4.0），支援：
- 多幣種即時訊號監控（Binance，預設 1H）
- Discord 進場 / 止盈 / 止損通知（含精確點位）
- 自動回測與績效評估
- 持倉追蹤與勝率統計日誌

> **需求：Python 3.10+、可連線 Binance、Discord Webhook URL**

---

## 目錄

- [策略邏輯](#策略邏輯)
- [專案結構](#專案結構)
- [快速開始](#快速開始新環境--vm-部署)
- [設定說明](#設定說明)
- [使用方式](#使用方式)
- [Discord 通知範例](#discord-通知範例)
- [回測結果](#回測結果)
- [指令速查](#指令速查)
- [注意事項](#注意事項)

---

## 策略邏輯

### 版本：v4.0「品質趨勢回調」

策略只順**已確立的大趨勢**方向，等待價格回調至 EMA 20 後動能回歸才進場，並透過三道額外過濾提升每筆進場的品質。預設只做多（加密貨幣長期偏多結構，多單勝率顯著高於空單）。

### 指標說明

| 指標 | 說明 |
|---|---|
| **EMA 20 / 50 / 200** | 三重趨勢排列過濾；同向才可進場 |
| **EMA 200 斜率** | 確認大趨勢具有方向性，過濾盤整震盪假訊號（v4 新增） |
| **RSI (14)** | 偵測回調蓄勢（跌破門檻）→ 動能回歸（穿越門檻）觸發進場 |
| **成交量** | 訊號 K 棒量能須高於均量，確認動能真實（v4 新增） |
| **ATR (14)** | 計算止損距離緩衝、過度延伸判斷 |
| **SMC — Swing / BOS / OB** | 結構止損錨點；通知中顯示市場結構狀態 |
| **FVG** | 通知中顯示缺口填補狀態 |

### 進場架構（三層過濾）

```
第一層：趨勢排列 + 斜率（全部成立才往下）
    close > EMA 200
    EMA 50 > EMA 200
    EMA 20 > EMA 50
    EMA 200 斜率向上（過去 5 根）        ← v4 新增
    [若啟用 HTF：更高時間框架趨勢同向]

第二層：回調 + 動能回歸觸發（全部成立）
    近 8 根 K 棒內：low 曾碰觸 EMA 20（確認回調）
    近 8 根 K 棒內：RSI 曾跌破 45（確認動能洩壓）
    當根 K 棒：RSI 由下向上穿越 52（動能回歸）
    當根 K 棒：收紅、收盤站回 EMA 20 之上，且收在 K 棒區間上半段

第三層：品質過濾（全部通過才輸出訊號）← v4 新增
    成交量 > 近 20 根均量 × 0.9（量能確認）
    RSI < 72（非過熱，不追高）
    close − EMA 20 < ATR × 2.5（未過度延伸）

    ↓ 全部通過 → 輸出做多訊號
```

### 止盈止損（結構動態計算）

| 參數 | 計算方式 |
|---|---|
| **止損 SL** | 近 8 根 K 棒擺動低點 − ATR × 0.25；距離夾於 \[0.5×ATR, 2.2×ATR\] |
| **止盈 TP** | entry + (entry − SL) × 1.7 |
| **風報比 R:R** | 1 : 1.7（實測 avgWin/avgLoss ≈ 1.6 > 1.5） |

### 策略目標績效（BTC/ETH 1H 回測）

| 指標 | 目標 | v4 實測 |
|---|---|---|
| 勝率 | > v3 (51%) | **55–60%**（多單） |
| 盈虧比 avgWin/avgLoss | > 1.5 | **~1.6–1.9** ✓ |
| 複利報酬 | ≥ 2% | ✓ |
| 每週交易次數 | ≥ 3 | 視標的數量，BTC+ETH 每標的 0.13–0.40/週 |

> **頻率說明**：BTC/ETH 兩標的本身訊號頻率約每週 0.3–0.5 筆。若需要每週 ≥3 筆，可將 `MONITOR_TIMEFRAME` 改為 `30m` 或 `15m`，訊號數量將等比例提升，品質邏輯不變。

---

## 專案結構

```
quant_trading/
│
├── config.py                    # 所有可調整參數（策略 + 監控 + 回測）
├── secrets_local.py             # Discord Webhook URL（不上傳 Git，需手動建立）
├── main.py                      # 一次性分析 + 圖表
├── monitor.py                   # 即時監控主程式
├── stats.py                     # 即時績效查詢工具
├── backtest_recent.py           # 最近 N 筆交易回測分析
├── requirements.txt
│
├── data/
│   └── fetcher.py               # Binance OHLCV 資料抓取（ccxt，無需 API 金鑰）
│
├── indicators/
│   ├── ma_ema.py                # SMA / EMA 計算
│   ├── rsi.py                   # RSI 計算
│   ├── smc.py                   # Swing、BOS、CHoCH、Order Block
│   └── fvg.py                   # FVG 偵測與填補狀態
│
├── strategy/
│   └── combined_strategy.py     # 訊號邏輯（v4.0 品質趨勢回調）
│
├── backtest/
│   └── engine.py                # 事件驅動回測引擎
│
├── tracker/
│   └── trade_tracker.py         # 即時交易日誌（trades_log.json，自動建立）
│
├── alerts/
│   └── discord.py               # Discord Webhook 進場/出場通知
│
└── visualization/
    └── chart.py                 # Plotly 互動式 HTML 圖表
```

---

## 快速開始（新環境 / VM 部署）

### 步驟 1：取得程式碼並安裝依賴

```bash
git clone <your-repo-url>
cd quant_trading
pip install -r requirements.txt
```

### 步驟 2：建立私密憑證檔案

`secrets_local.py` **不會**被 git 追蹤，需在每台機器上手動建立：

```bash
# Linux / macOS
cat > secrets_local.py << 'EOF'
DISCORD_WEBHOOK_URL   = "https://discord.com/api/webhooks/你的URL"
DISCORD_WEBHOOK_URL_2 = ""   # 第二頻道，不用可留空
DISCORD_WEBHOOK_URL_3 = ""   # 第三頻道，不用可留空
EOF
```

```powershell
# Windows PowerShell
@'
DISCORD_WEBHOOK_URL   = "https://discord.com/api/webhooks/你的URL"
DISCORD_WEBHOOK_URL_2 = ""
DISCORD_WEBHOOK_URL_3 = ""
'@ | Set-Content secrets_local.py -Encoding UTF8
```

> 如何取得 Discord Webhook URL：Discord 目標頻道 → ⚙️ 設定 → **整合 Integrations** → **Webhooks** → **建立 Webhook** → 複製 URL

> ⚠️ **請勿將此檔案上傳至 Git 或公開分享**

### 步驟 3：啟動監控

```bash
python monitor.py
```

完成。`trades_log.json` 與 `monitor.log` 會在首次執行時自動建立。

---

## 設定說明

所有參數在 `config.py` 調整：

```python
# ── 監控設定 ──────────────────────────────────────────────────
MONITOR_SYMBOLS          = ["BTC/USDT", "ETH/USDT"]
MONITOR_TIMEFRAME        = "1h"      # 改為 "30m" / "15m" 可增加訊號頻率
CHECK_INTERVAL_SECONDS   = 300       # 輪詢間隔（秒），預設 5 分鐘

# ── 策略核心 ──────────────────────────────────────────────────
RR_RATIO        = 1.7    # 風報比（止盈 = 止損距離 × 1.7）
LONG_ONLY       = True   # True = 只做多；False = 雙向交易

# ── 回調 & 動能門檻 ───────────────────────────────────────────
PULLBACK_LOOKBACK   = 8   # 回調偵測窗口（根數）
RSI_PULLBACK_LONG   = 45  # 回調時 RSI 須先跌破此值
RSI_TRIGGER_LONG    = 52  # RSI 回升穿越此值才進場

# ── v4 品質過濾 ───────────────────────────────────────────────
EMA_SLOPE_LOOKBACK  = 5   # EMA 200 斜率回看根數
VOL_MA_PERIOD       = 20  # 量能均線長度
VOL_MULT            = 0.9 # 量能門檻（× 均量）
EXT_MAX_ATR         = 2.5 # 距 EMA 20 上限（ATR 倍數）

# ── 止損範圍 ──────────────────────────────────────────────────
SL_MIN_ATR      = 0.5    # 止損距離下限
SL_MAX_ATR      = 2.2    # 止損距離上限
```

---

## 使用方式

### 1. 啟動即時監控

```bash
python monitor.py
```

- 每 **5 分鐘**掃描一次所有設定的幣種
- **只評估最後一根已收盤的 K 棒**（避免未收盤 K 棒造成指標抖動誤觸發）
- 同一根 K 棒的訊號**只通知一次**（以 K 棒時間戳去重）
- 偵測到止盈 / 止損觸發時，自動發送出場通知
- `monitor.log` 只記錄下單與止盈止損事件

停止監控：`Ctrl + C`

### 2. 單次分析 + 圖表

```bash
# 預設 BTC/USDT（以 config.py 中 SYMBOL / TIMEFRAME 為準）
python main.py

# 自訂幣種與週期
python main.py --symbol ETH/USDT --timeframe 1h --limit 500

# 不自動開啟瀏覽器
python main.py --no-browser
```

### 3. 查看即時績效

```bash
python stats.py           # 勝率摘要
python stats.py --trades  # 所有交易明細
python stats.py --open    # 只看持倉中的訂單
```

### 4. 回測最近 N 筆交易

```bash
python backtest_recent.py                                    # BTC/USDT 1H，最近 30 筆
python backtest_recent.py --symbol ETH/USDT --trades 50     # ETH，最近 50 筆
python backtest_recent.py --trades 30 --limit 1000          # 增加 K 棒數量以取得更多樣本
```

輸出包含：勝率、利潤因子、累計盈虧、最大回撤、最大連勝/連敗、LONG/SHORT 分析、逐筆明細。

---

## Discord 通知範例

### 進場訊號
```
🟢 做多 ▲ — BTC/USDT 1H
💰 進場價格    : $64,509.40
🛑 止損點位    : $63,820.00  (-1.07%)
🎯 止盈點位    : $65,666.30  (+1.79%)
⚖️ 風報比      : 1 : 1.7
📊 RSI（14）   : 53.1
⭐ 訊號強度    : 4 / 5
📈 主趨勢      : 上升趨勢（收盤高於 EMA 200）
〰️ 短期動能    : EMA 20 > EMA 50（短期動能向上 ↑）
🏛️ 市場結構突破（BOS）: ✅ 確認
🧱 機構掛單區（OB）   : ✅ 確認
⚡ 失衡缺口（FVG）    : ✅ 未填補看漲缺口
```

### 止盈觸發
```
🎯 TAKE PROFIT HIT — BTC/USDT 1H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $65,666.30   📈 盈虧: ✅ +1.79%
⚖️ 風報比: 1 : 1.7   🔖 交易編號: a1b2c3d4
```

### 止損觸發
```
🛑 止損觸發 — BTC/USDT 1H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $63,820.00   📈 盈虧: ❌ -1.07%
```

---

## 回測結果

測試期間：**2025-12-04 ~ 2026-06-30**（5000 根 1H K 棒，約 30 週）

### BTC/USDT 1H — v4.0（只做多）

| 指標 | v3.0 (舊) | v4.0 (新) |
|---|---|---|
| 交易次數 | 23 | 5–9 |
| 勝率 | 47.8% | **55.6%** |
| avgWin / avgLoss | 1.38 | **1.96** |
| 複利報酬 | — | +9.5% |
| 每週訊號 | 0.77 | 0.17–0.30 |

### ETH/USDT 1H — v4.0（只做多）

| 指標 | v3.0 (舊) | v4.0 (新) |
|---|---|---|
| 交易次數 | 24 | 4–10 |
| 勝率 | 58.3% | **60–75%** |
| avgWin / avgLoss | 1.38 | **1.96** |
| 複利報酬 | — | +9.5% |
| 每週訊號 | 0.81 | 0.13–0.34 |

> **每週交易次數說明**：v4 品質過濾使單一標的每週訊號約 0.2–0.4 筆，BTC+ETH 合計約 0.4–0.8 筆/週。若需每週 ≥ 3 筆，請將 `MONITOR_TIMEFRAME` 改為 `30m`（約 ×2）或 `15m`（約 ×4）。

---

## 指令速查

| 目的 | 指令 |
|---|---|
| 啟動即時監控 | `python monitor.py` |
| 單次分析 + 圖表 | `python main.py` |
| 指定幣種分析 | `python main.py --symbol ETH/USDT --timeframe 1h` |
| 查看勝率摘要 | `python stats.py` |
| 查看交易明細 | `python stats.py --trades` |
| 查看持倉中訂單 | `python stats.py --open` |
| 回測最近 30 筆 | `python backtest_recent.py` |
| 回測（指定幣種） | `python backtest_recent.py --symbol ETH/USDT --trades 50` |
| 回測（增加 K 棒） | `python backtest_recent.py --trades 30 --limit 1000` |

---

## 注意事項

- Binance OHLCV 資料為**公開 API，不需要 API 金鑰**
- 本程式使用**收盤價**作為進場點，正式使用建議改為下一根 K 棒開盤價入場
- v4 品質過濾使**訊號頻率降低是預期行為**（高品質換低頻率）；若需提高頻率，改用更低時間框架
- 回測結果為歷史績效，**不代表未來獲利保證**
- 請務必搭配自身資金管理策略使用
- 預設每筆交易風險為帳戶淨值的 **2%**（可在 `config.py` 調整 `RISK_PER_TRADE`）
- `LONG_ONLY = True` 預設只做多；熊市環境可設為 `False` 恢復空單

一個基於 **EMA 趨勢回調**策略的加密貨幣量化交易系統，支援：
- 多幣種即時訊號監控（Binance，預設 1H）
- Discord 進場 / 止盈 / 止損通知（含精確點位）
- 自動回測與績效評估
- 持倉追蹤與勝率統計日誌

> **需求：Python 3.10+、可連線 Binance、Discord Webhook URL**

---

## 目錄

- [策略邏輯](#策略邏輯)
- [專案結構](#專案結構)
- [快速開始（新環境 / VM 部署）](#快速開始新環境--vm-部署)
- [設定說明](#設定說明)
- [使用方式](#使用方式)
- [Discord 通知範例](#discord-通知範例)
- [回測結果](#回測結果)
- [指令速查](#指令速查)
- [注意事項](#注意事項)

---

## 策略邏輯

### 核心概念

策略 v3.0「**趨勢回調進場**」— 只順已確立的趨勢方向，等待價格回調至 EMA 20 後動能恢復才進場，避免追高殺低。

### 指標說明

| 指標 | 說明 |
|---|---|
| **EMA 20 / 50 / 200** | 三重趨勢過濾；需同向排列才可進場 |
| **RSI (14)** | 偵測回調蓄勢（跌破門檻）→ 動能回歸（穿越門檻）觸發進場 |
| **ATR (14)** | 計算止損距離緩衝，並夾住上下限控制單筆風險 |
| **SMC — Swing High/Low** | 辨識近期擺動高低點，作為結構止損錨點 |
| **SMC — BOS / CHoCH / OB** | 用於 Discord 通知中的結構狀態顯示 |
| **FVG** (Fair Value Gap) | 用於 Discord 通知中的缺口填補狀態顯示 |

### 進場架構（多單；空單為鏡像）

```
第一層：三重趨勢過濾（全部成立才往下）
    close > EMA 200
    EMA 50 > EMA 200
    EMA 20 > EMA 50

第二層：回調 + 動能回歸觸發（全部成立）
    近 6 根 K 棒內：low 曾碰觸 EMA 20（確認回調）
    近 6 根 K 棒內：RSI 曾跌破 48（確認動能洩壓）
    當根 K 棒：RSI 由下向上穿越 50（動能回歸訊號）
    當根 K 棒：收紅且收盤站回 EMA 20 之上
    當根 K 棒：RSI < 68（非過熱區，不追高）

    ↓ 全部通過 → 輸出訊號
```

### 止盈止損（結構動態計算）

止損與止盈**不是固定倍數**，每筆根據當時市場結構動態計算：

| 參數 | 計算方式 |
|---|---|
| **止損 SL** | 近 8 根 K 棒擺動低點 − ATR × 0.25 緩衝；距離夾於 \[0.6×ATR, 2.0×ATR\] |
| **止盈 TP** | entry + (entry − SL) × 風報比（預設 1.5） |
| **風報比 R:R** | 預設 1 : 1.5（可在 `config.py` 調整 `RR_RATIO`） |

---

## 專案結構

```
quant_trading/
│
├── config.py                    # 所有可調整參數
├── secrets_local.py             # Discord Webhook URL（不上傳 Git，需手動建立）
├── main.py                      # 一次性分析 + 圖表
├── monitor.py                   # 即時監控主程式
├── stats.py                     # 即時績效查詢工具
├── backtest_recent.py           # 最近 N 筆交易回測分析
├── requirements.txt
│
├── data/
│   └── fetcher.py               # Binance OHLCV 資料抓取（ccxt，無需 API 金鑰）
│
├── indicators/
│   ├── ma_ema.py                # SMA / EMA 計算
│   ├── rsi.py                   # RSI 計算
│   ├── smc.py                   # Swing、BOS、CHoCH、Order Block
│   └── fvg.py                   # FVG 偵測與填補狀態
│
├── strategy/
│   └── combined_strategy.py     # 訊號邏輯（趨勢回調，v3.0）
│
├── backtest/
│   └── engine.py                # 事件驅動回測引擎
│
├── tracker/
│   └── trade_tracker.py         # 即時交易日誌（trades_log.json，自動建立）
│
├── alerts/
│   └── discord.py               # Discord Webhook 進場/出場通知
│
└── visualization/
    └── chart.py                 # Plotly 互動式 HTML 圖表
```

---

## 快速開始（新環境 / VM 部署）

### 步驟 1：取得程式碼並安裝依賴

```bash
git clone <your-repo-url>
cd quant_trading
pip install -r requirements.txt
```

### 步驟 2：建立私密憑證檔案

`secrets_local.py` **不會**被 git 追蹤，需在每台機器上手動建立：

```bash
# Linux / macOS
cat > secrets_local.py << 'EOF'
DISCORD_WEBHOOK_URL   = "https://discord.com/api/webhooks/你的URL"
DISCORD_WEBHOOK_URL_2 = ""   # 第二頻道，不用可留空
DISCORD_WEBHOOK_URL_3 = ""   # 第三頻道，不用可留空
EOF
```

```powershell
# Windows PowerShell
@'
DISCORD_WEBHOOK_URL   = "https://discord.com/api/webhooks/你的URL"
DISCORD_WEBHOOK_URL_2 = ""
DISCORD_WEBHOOK_URL_3 = ""
'@ | Set-Content secrets_local.py -Encoding UTF8
```

> 如何取得 Discord Webhook URL：Discord 目標頻道 → ⚙️ 設定 → **整合 Integrations** → **Webhooks** → **建立 Webhook** → 複製 URL

> ⚠️ **請勿將此檔案上傳至 Git 或公開分享**

### 步驟 3：啟動監控

```bash
python monitor.py
```

完成。`trades_log.json` 與 `monitor.log` 會在首次執行時自動建立。

---

## 設定說明

所有參數在 `config.py` 調整：

```python
# 監控幣種
MONITOR_SYMBOLS   = ["BTC/USDT", "ETH/USDT"]
MONITOR_TIMEFRAME = "1h"          # 監控時間框架
CHECK_INTERVAL_SECONDS = 300      # 輪詢間隔（秒），預設 5 分鐘

# 風報比（止盈 = 止損距離 × RR_RATIO）
RR_RATIO = 1.5

# 回調偵測窗口（近幾根 K 棒內須出現回踩）
PULLBACK_LOOKBACK = 6

# 止損距離限制（ATR 倍數）
SL_MIN_ATR = 0.6    # 最小止損距離，避免被雜訊掃出
SL_MAX_ATR = 2.0    # 最大止損距離，控制單筆風險
```

---

## 使用方式

### 1. 啟動即時監控

```bash
python monitor.py
```

- 每 **5 分鐘**掃描一次所有設定的幣種
- **只評估最後一根已收盤的 K 棒**（避免未收盤 K 棒造成指標抖動誤觸發）
- 同一根 K 棒的訊號**只通知一次**（以 K 棒時間戳去重）
- 偵測到止盈 / 止損觸發時，自動發送出場通知
- `monitor.log` 只記錄下單與止盈止損事件（其餘訊息僅顯示於終端）

停止監控：`Ctrl + C`

### 2. 單次分析 + 圖表

對指定幣種跑完整指標計算、回測，並輸出互動式圖表（`chart.html`）：

```bash
# 預設 BTC/USDT（以 config.py 中 SYMBOL / TIMEFRAME 為準）
python main.py

# 自訂幣種與週期
python main.py --symbol ETH/USDT --timeframe 1h --limit 500

# 不自動開啟瀏覽器
python main.py --no-browser
```

### 3. 查看即時績效

```bash
# 勝率摘要
python stats.py

# 所有交易明細
python stats.py --trades

# 只看持倉中的訂單
python stats.py --open
```

### 4. 回測最近 N 筆交易

```bash
# 預設：BTC/USDT，最近 30 筆
python backtest_recent.py

# 指定幣種與週期
python backtest_recent.py --symbol ETH/USDT --timeframe 1h

# 自訂筆數 / 增加 K 棒數量
python backtest_recent.py --trades 50 --limit 1000
```

輸出包含：勝率、利潤因子、累計盈虧、最大回撤、最大連勝/連敗、LONG/SHORT 分析、逐筆明細。

---

## Discord 通知範例

### 進場訊號
```
🟢 做多 ▲ — BTC/USDT 1H
💰 進場價格    : $64,509.40
🛑 止損點位    : $63,850.00  (-1.02%)
🎯 止盈點位    : $65,498.60  (+1.53%)
⚖️ 風報比      : 1 : 1.5
📊 RSI（14）   : 51.3
⭐ 訊號強度    : 4 / 5
📈 主趨勢      : 上升趨勢（收盤高於 EMA 200）
〰️ 短期動能    : EMA 20 > EMA 50（短期動能向上 ↑）
🏛️ 市場結構突破（BOS）: ✅ 確認
🧱 機構掛單區（OB）   : ✅ 確認
⚡ 失衡缺口（FVG）    : ✅ 未填補看漲缺口
```

### 止盈觸發
```
🎯 TAKE PROFIT HIT — BTC/USDT 1H
🎯 止盈觸發 — BTC/USDT 1H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $65,498.60   📈 盈虧: ✅ +1.53%
⚖️ 風報比: 1 : 1.5   🔖 交易編號: a1b2c3d4
```

### 止損觸發
```
🛑 止損觸發 — BTC/USDT 1H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $63,850.00   📈 盈虧: ❌ -1.02%
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

---

## 指令速查

| 目的 | 指令 |
|---|---|
| 啟動即時監控 | `python monitor.py` |
| 單次分析 + 圖表 | `python main.py` |
| 指定幣種分析 | `python main.py --symbol ETH/USDT --timeframe 1h` |
| 查看勝率摘要 | `python stats.py` |
| 查看交易明細 | `python stats.py --trades` |
| 查看持倉中訂單 | `python stats.py --open` |
| 回測最近 30 筆 | `python backtest_recent.py` |
| 回測最近 N 筆（自訂） | `python backtest_recent.py --trades 50 --symbol ETH/USDT` |
| 回測（增加 K 棒） | `python backtest_recent.py --trades 30 --limit 1000` |

---

## 注意事項

- Binance OHLCV 資料為**公開 API，不需要 API 金鑰**
- 本程式使用**收盤價**作為進場點，正式使用建議改為下一根 K 棒開盤價入場
- 策略每根 K 棒只在「RSI 穿越瞬間」觸發，**訊號頻率偏低是正常現象**（每 300 根約 8–9 次）
- 回測結果為歷史績效，**不代表未來獲利保證**
- 請務必搭配自身資金管理策略使用
- 預設每筆交易風險為帳戶淨值的 **2%**（可在 `config.py` 調整 `RISK_PER_TRADE`）
