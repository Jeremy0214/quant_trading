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
STOP_LOSS_ATR_MULT  = 2.0
TAKE_PROFIT_ATR_MULT = 4.0

# --- Exchange ---
EXCHANGE = "binance"

# ============================================================
# Monitor / Alert Settings
# ============================================================

# Symbols to monitor simultaneously
MONITOR_SYMBOLS = ["BTC/USDT", "ETH/USDT"]
MONITOR_TIMEFRAME = "4h"
MONITOR_LIMIT = 300          # candles to fetch per check

# How often (seconds) to poll Binance for new candles
# 4H candle = 14400 s; checking every 5 min catches the close quickly
CHECK_INTERVAL_SECONDS = 300  # 5 minutes

# ── Discord Webhook ──────────────────────────────────────────
# 1. Open Discord → Channel Settings → Integrations → Webhooks → New Webhook
# 2. Copy the URL and paste it below (keep it private, do NOT commit to git)
DISCORD_WEBHOOK_URL = "https://discord.com/api/webhooks/1517418759281971262/sQbGI9DSuHwhAVZZLaqRX3xyM05Q30upjUbN8vbLKBThekAunZqlM-f-Loh5Y9NYFVIe"   # ← 填入你的 Webhook URL
