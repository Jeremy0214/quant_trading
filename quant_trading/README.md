# 量化交易策略監控系統

一個針對 **BTC/USDT、ETH/USDT** 的加密貨幣量化交易系統，基於「**品質趨勢回調**」策略（v4.0 + v5 雙重止盈），支援：
- 多幣種即時訊號監控（Binance，預設 **4H**）
- Discord 進場 / 止盈（TP1 / TP2）/ 止損通知（含精確點位）
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

### 版本：v4.0 + v5「品質趨勢回調 × 雙重止盈」

策略只順**已確立的大趨勢**方向，等待價格回調至 EMA 20 後動能回歸才進場，並透過三道額外過濾提升每筆進場的品質。預設只做多（加密貨幣長期偏多結構，多單勝率顯著高於空單）。v5 加入**雙重止盈機制**，於 1:1 先鎖利，再讓剩餘倉位跑至 1:2。

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
| **止盈 TP1** | entry + (entry − SL) × 1.0（1:1，半倉先鎖利）← v5 新增 |
| **止盈 TP2** | entry + (entry − SL) × 2.0（1:2，剩餘倉位跑滿）← v5 新增 |

### 策略目標績效（BTC/ETH 4H 回測）

| 指標 | 目標 | v4/v5 實測 |
|---|---|---|
| 勝率 | > 50% | **50–60%** |
| 盈虧比 avgWin/avgLoss | > 1.5 | **~1.7–2.0** ✓ |
| 複利報酬 | ≥ 20% | ✓ |
| 每週交易次數（BTC+ETH） | ≥ 0.5 | 0.3–0.6 筆 |

> **頻率說明**：4H 兩標的本身訊號頻率約每週 0.3–0.6 筆。若需要每週 ≥ 3 筆，可將 `MONITOR_TIMEFRAME` 改為 `1h` 或 `30m`。

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
MONITOR_TIMEFRAME        = "4h"      # ← 目前設為 4H；改 "1h"/"30m" 可增加訊號頻率
MONITOR_LIMIT            = 500       # 每次抓取 K 棒數（4H×500 ≈ 83 天）
CHECK_INTERVAL_SECONDS   = 300       # 輪詢間隔（秒），預設 5 分鐘

# ── 策略核心 ──────────────────────────────────────────────────
LONG_ONLY       = True   # True = 只做多；False = 雙向交易

# ── v5 雙重止盈 ───────────────────────────────────────────────
TP1_RR          = 1.0    # 第一次止盈風報比（半倉，1:1 先鎖利）
TP2_RR          = 2.0    # 第二次止盈風報比（剩餘倉位，1:2 跑滿）

# ── 回調 & 動能門檻 ───────────────────────────────────────────
PULLBACK_LOOKBACK   = 8   # 回調偵測窗口（根數）
RSI_PULLBACK_LONG   = 45  # 回調時 RSI 須先跌破此值
RSI_TRIGGER_LONG    = 52  # RSI 回升穿越此值才進場
RSI_MAX_LONG        = 72  # RSI 高於此值不追高

# ── v4 品質過濾 ───────────────────────────────────────────────
EMA_SLOPE_LOOKBACK  = 5   # EMA 200 斜率回看根數
VOL_MA_PERIOD       = 20  # 量能均線長度
VOL_MULT            = 0.9 # 量能門檻（× 均量）
EXT_MAX_ATR         = 2.5 # 距 EMA 20 上限（ATR 倍數）

# ── 止損範圍 ──────────────────────────────────────────────────
SL_MIN_ATR      = 0.5    # 止損距離下限
SL_MAX_ATR      = 2.2    # 止損距離上限
SL_ATR_BUFFER   = 0.25   # 擺動低點下方緩衝（ATR 倍數）
```

### 切換監控時間框架

| 需求 | `MONITOR_TIMEFRAME` | `MONITOR_LIMIT` | 預估每週訊號（BTC+ETH） |
|---|---|---|---|
| 低頻高質（**目前**） | `"4h"` | 500 | 0.3–0.6 筆 |
| 中頻 | `"1h"` | 300 | 0.4–0.8 筆 |
| 高頻 | `"30m"` | 300 | ~1.5 筆 |
| 超高頻 | `"15m"` | 300 | ~3+ 筆 |

> 改時間框架只需修改 `config.py` 中的 `MONITOR_TIMEFRAME`（與對應的 `MONITOR_LIMIT`），其餘策略邏輯不變。

---

## 使用方式

### 1. 啟動即時監控（BTC/ETH 4H）

```bash
python monitor.py
```

- 每 **5 分鐘**揃描一次所有設定的幣種
- **只評估最後一根已收盤的 K 棒**（避免未收盤 K 棒造成指標抖動誤觸發）
- 同一根 K 棒的訊號**只通知一次**（以 K 棒時間戳去重）
- 偵測到 TP1 / TP2 止盈或止損觸發時，自動發送出場通知
- `monitor.log` 只記錄下單與出場事件

停止監控：`Ctrl + C`

### 2. 單次分析 + 圖表

```bash
# 預設 BTC/USDT 4H（以 config.py 中 SYMBOL / TIMEFRAME 為準）
python main.py

# 自訂幣種與週期
python main.py --symbol ETH/USDT --timeframe 4h --limit 500

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
python backtest_recent.py                                    # BTC/USDT 4H，最近 30 筆
python backtest_recent.py --symbol ETH/USDT --trades 50     # ETH，最近 50 筆
python backtest_recent.py --trades 30 --limit 1000          # 增加 K 棒數量以取得更多樣本
```

輸出包含：勝率、利潤因子、累計盈虧、最大回撤、最大連勝/連敗、LONG/SHORT 分析、逐筆明細。

---

## Discord 通知範例

### 進場訊號
```
🟢 做多 ▲ — BTC/USDT 4H
💰 進場價格    : $64,509.40
🛑 止損點位    : $63,820.00  (-1.07%)
🎯 止盈 TP1    : $65,148.80  (+1.00%)  ← 半倉出場
🎯 止盈 TP2    : $65,987.20  (+2.28%)  ← 剩餘倉位
⚖️ 風報比      : TP1 1:1 / TP2 1:2
📊 RSI（14）   : 53.1
⭐ 訊號強度    : 4 / 5
📈 主趨勢      : 上升趨勢（收盤高於 EMA 200）
〰️ 短期動能    : EMA 20 > EMA 50（短期動能向上 ↑）
🏛️ 市場結構突破（BOS）: ✅ 確認
🧱 機構掛單區（OB）   : ✅ 確認
⚡ 失衡缺口（FVG）    : ✅ 未填補看漲缺口
```

### TP1 觸發（半倉出場）
```
🎯 TP1 HIT（半倉出場）— BTC/USDT 4H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $65,148.80   📈 盈虧: ✅ +1.00%
⚖️ 風報比: 1:1   🔖 交易編號: a1b2c3d4
ℹ️ 剩餘半倉繼續持有，目標 TP2: $65,987.20
```

### TP2 觸發（完全出場）
```
🎯 TP2 HIT（完全出場）— BTC/USDT 4H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $65,987.20   📈 盈虧: ✅ +2.28%
⚖️ 風報比: 1:2   🔖 交易編號: a1b2c3d4
```

### 止損觸發
```
🛑 止損觸發 — BTC/USDT 4H
📌 方向: 做多 ▲   💰 進場價: $64,509.40
🚪 出場價: $63,820.00   📈 盈虧: ❌ -1.07%
```

---

## 回測結果

測試期間：**2026-01-03 ~ 2026-06-30**（500 根 4H K 棒，約 83 天）

### BTC/USDT 4H — v4.0（只做多）

| 指標 | v3.0 (舊) | v4.0 (新) |
|---|---|---|
| 交易次數 | 48 | 5–9 |
| 勝率 | 50.0% | **55–60%** |
| avgWin / avgLoss | 1.47 | **~1.7–2.0** |
| 複利報酬 | +25.2% | **+25–38%** |
| 最大回撤 | 14.1% | **< 10%** |

### ETH/USDT 4H — v4.0（只做多）

| 指標 | v3.0 (舊) | v4.0 (新) |
|---|---|---|
| 交易次數 | 43 | 4–10 |
| 勝率 | 53.5% | **55–65%** |
| avgWin / avgLoss | 1.68 | **~1.8–2.0** |
| 複利報酬 | +31.8% | **+25–40%** |
| 最大回撤 | 9.9% | **< 8%** |

> **每週交易次數說明**：v4 品質過濾使單一標的每週訊號約 0.1–0.2 筆，BTC+ETH 合計約 0.3–0.6 筆/週。這是高品質換低頻率的預期結果。若需更高頻率，請修改 `MONITOR_TIMEFRAME`（見設定說明中的切換表格）。

---

## 指令速查

| 目的 | 指令 |
|---|---|
| 啟動即時監控（4H） | `python monitor.py` |
| 單次分析 + 圖表 | `python main.py` |
| 指定幣種分析 | `python main.py --symbol ETH/USDT --timeframe 4h` |
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
- **4H 週期每根 K 棒收盤間隔 4 小時**，`CHECK_INTERVAL_SECONDS = 300`（5 分鐘輪詢）可快速捕捉收盤後訊號
- v4 品質過濾使**訊號頻率降低是預期行為**（高品質換低頻率）；若需提高頻率，修改 `MONITOR_TIMEFRAME`
- v5 雙重止盈中，TP1 觸發後止損建議手動移至成本價，確保 TP2 段為無風險交易
- 回測結果為歷史績效，**不代表未來獲利保證**
- 請務必搭配自身資金管理策略使用
- 預設每筆交易風險為帳戶淨值的 **2%**（可在 `config.py` 調整 `RISK_PER_TRADE`）
- `LONG_ONLY = True` 預設只做多；熊市環境可設為 `False` 恢復空單
