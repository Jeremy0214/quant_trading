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

# --- RSI ---
RSI_PERIOD      = 14
RSI_OVERBOUGHT  = 70
RSI_OVERSOLD    = 30

# --- SMC ---
SMC_SWING_LENGTH = 10   # Lookback for swing high / swing low detection

# --- Backtest ---
INITIAL_CAPITAL     = 10_000   # USDT
RISK_PER_TRADE      = 0.02     # 2 % risk per trade
STOP_LOSS_ATR_MULT  = 2.0      # fallback only (used when no structural SL found)
TAKE_PROFIT_ATR_MULT = 4.0     # fallback only

# ============================================================
# Strategy v3.0 — Trend-Pullback + Structural SL/TP
# ============================================================
# 止損(SL)以「市場結構」為依據（近期擺動低/高點 + ATR 緩衝），
# 止盈(TP)以「實際風險距離 × 風報比」為依據（非固定點數）。
# 因此每筆交易的 SL/TP 都會隨結構與波動動態變化。

# 風報比（TP = entry ± risk × RR_RATIO）— 必須 ≥ 1.5
RR_RATIO            = 1.5

# 結構止損：取最近 N 根 K 棒的擺動低/高點作為止損錨點
SL_SWING_LOOKBACK   = 8
# 止損緩衝：在結構點之外再留 ATR × buffer，避免被插針掃損
SL_ATR_BUFFER       = 0.25
# 止損距離上限（ATR 倍數）：結構點太遠時，改用此上限以控制單筆風險
SL_MAX_ATR          = 2.0
# 止損距離下限（ATR 倍數）：避免止損過近被雜訊掃出
SL_MIN_ATR          = 0.6

# 進場動能門檻（RSI）
RSI_PULLBACK_LONG   = 48   # 多單：回調時 RSI 須先跌破此值（蓄勢）
RSI_TRIGGER_LONG    = 50   # 多單：RSI 由下向上穿越此值才進場
RSI_MAX_LONG        = 68   # 多單：RSI 高於此值視為過熱，不追高
RSI_PULLBACK_SHORT  = 52   # 空單：反彈時 RSI 須先升破此值
RSI_TRIGGER_SHORT   = 50   # 空單：RSI 由上向下穿越此值才進場
RSI_MIN_SHORT       = 32   # 空單：RSI 低於此值視為超賣，不追空

# 回調偵測窗口：近 N 根 K 棒內須出現對 EMA20 的回踩/反彈
PULLBACK_LOOKBACK   = 6

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