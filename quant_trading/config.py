# ============================================================
# Quantitative Trading Strategy — Configuration
# ============================================================

# --- Trading Pair & Timeframe ---
SYMBOL = "BTC/USDT"
TIMEFRAME = "4h" 
LIMIT = 500          # Number of candles to fetch

# --- MA / EMA Periods ---
EMA_SHORT  = 20
EMA_LONG   = 50
EMA_TREND  = 200
EMA_FILTER = 56    # Directional bias: close > EMA_56 → long only; close < EMA_56 → short only

# --- RSI ---
RSI_PERIOD      = 14
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# --- SMC ---
SMC_SWING_LENGTH    = 10   # Lookback for swing high / swing low detection
OB_ACTIVE_LOOKBACK  = 30   # Bars an OB zone stays active before it is considered stale

# --- Backtest ---
INITIAL_CAPITAL     = 10_000   # USDT
RISK_PER_TRADE      = 0.02     # 2 % risk per trade
STOP_LOSS_ATR_MULT  = 2.0      # fallback only (used when no structural SL found)
TAKE_PROFIT_ATR_MULT = 4.0     # fallback only

# ============================================================
# Strategy v4.0 — Quality Trend-Pullback + Structural SL/TP
# ============================================================
# 在 v3 三層進場架構的基礎上新增三道勝率過濾：
#   (a) EMA 200 斜率過濾  — 只在趨勢有「方向感」時交易
#   (b) 量能確認          — 訊號 K 棒量能須高於均量
#   (c) 過度延伸過濾      — 距 EMA 20 超過 ATR 上限不追
# 目標風報比拉高至 1.7，預設只做多（加密貨幣長期偏多）。

# 風報比（TP = entry ± risk × RR_RATIO）
RR_RATIO            = 1.7   # v4 拉高至 1.7（實測 avgWin/avgLoss ≈ 1.6）

# ── v5 雙重止盈 ─────────────────────────────────────────────────────────────
# 第一次止盈 1:1，第二次止盈 1:2，各代表半倉出場
TP1_RR              = 1.0   # 第一次止盈（1:1 風報比）
TP2_RR              = 2.0   # 第二次止盈（1:2 風報比）

# 只做多：加密貨幣多單勝率(~59%)顯著高於空單(~45%)，預設關閉空單
LONG_ONLY           = True  # 設為 False 可恢復雙向交易

# 結構止損：取最近 N 根 K 棒的擺動低/高點作為止損錨點
SL_SWING_LOOKBACK   = 8
# 止損緩衝：在結構點之外再留 ATR × buffer，避免被插針掃損
SL_ATR_BUFFER       = 0.25
# 止損距離上限（ATR 倍數）：結構點太遠時，改用此上限以控制單筆風險
SL_MAX_ATR          = 2.2
# 止損距離下限（ATR 倍數）：避免止損過近被雜訊掃出
SL_MIN_ATR          = 0.5

# 進場動能門檻（RSI）
RSI_PULLBACK_LONG   = 45   # 多單：回調時 RSI 須先跌破此值（蓄勢）
RSI_TRIGGER_LONG    = 52   # 多單：RSI 由下向上穿越此值才進場（v4 提高至 52）
RSI_MAX_LONG        = 72   # 多單：RSI 高於此值視為過熱，不追高
RSI_PULLBACK_SHORT  = 55   # 空單：反彈時 RSI 須先升破此值
RSI_TRIGGER_SHORT   = 48   # 空單：RSI 由上向下穿越此值才進場
RSI_MIN_SHORT       = 28   # 空單：RSI 低於此值視為超賣，不追空

# 回調偵測窗口：近 N 根 K 棒內須出現對 EMA20 的回踩/反彈
PULLBACK_LOOKBACK   = 8    # v4 擴大至 8（捕捉較深回調）

# ── v4 新增：勝率提升三道過濾 ──────────────────────────────────
# EMA 200 斜率：比較前 N 根，確認趨勢真正有方向（過濾盤整假訊號）
EMA_SLOPE_LOOKBACK  = 5
# 量能確認：訊號 K 棒成交量須高於近 N 根均量的 VOL_MULT 倍
VOL_MA_PERIOD       = 20
VOL_MULT            = 0.9
# 過度延伸：收盤距 EMA 20 超過 EXT_MAX_ATR 倍 ATR 時不進場（避免追高）
EXT_MAX_ATR         = 2.5

# --- Exchange ---
EXCHANGE = "binance"

# ============================================================
# Monitor / Alert Settings
# ============================================================

# Symbols to monitor simultaneously
MONITOR_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
MONITOR_TIMEFRAME = "1h"
MONITOR_LIMIT = 300          # candles to fetch per check

# How often (seconds) to poll Binance for new candles
# 4H candle = 14400 s; checking every 5 min catches the close quickly
CHECK_INTERVAL_SECONDS = 300  # 5 minutes

# ── Discord Webhook ──────────────────────────────────────────
# Webhook URLs 存放於 secrets_local.py（已加入 .gitignore，不會上傳）。
# 若 secrets_local.py 不存在，則預設為空字串（不發送 Discord 通知）。
try:
    from secrets_local import DISCORD_WEBHOOK_URL, DISCORD_WEBHOOK_URL_2, DISCORD_WEBHOOK_URL_3 # noqa: F401
except ImportError:
    DISCORD_WEBHOOK_URL   = ""  # 請在 secrets_local.py 填入 Webhook URL
    DISCORD_WEBHOOK_URL_2 = ""
    DISCORD_WEBHOOK_URL_3 = ""