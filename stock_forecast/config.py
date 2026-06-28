"""
台股評估系統 — 參數設定
"""

# ── 股票後綴 ────────────────────────────────────────────
SUFFIXES = ['.TW', '.TWO']   # 上市先試，上櫃次之

# ── 技術指標期間 ─────────────────────────────────────────
MA_SHORT   = 5
MA_MEDIUM  = 20
MA_LONG    = 60
RSI_PERIOD = 14
MACD_FAST   = 12
MACD_SLOW   = 26
MACD_SIGNAL = 9

# ── 基本面門檻 ───────────────────────────────────────────
REVENUE_YOY_HIGH   = 10.0   # 月 YoY > 10% → 滿分
PE_LOW_THRESHOLD   = 15.0   # P/E < 15  → 滿分
PE_MED_THRESHOLD   = 20.0   # P/E 15-20 → 半分
PE_HIGH_THRESHOLD  = 25.0   # P/E > 25  → 0分
ROE_HIGH_THRESHOLD = 15.0   # ROE > 15% → 滿分
ROE_MED_THRESHOLD  = 10.0   # ROE 10%~15% → 半分

# ── 技術面門檻 ───────────────────────────────────────────
RSI_OVERBOUGHT      = 80
RSI_UPPER           = 70
RSI_LOWER           = 40
RSI_OVERSOLD        = 20
VOLUME_INCREASE_RATIO = 1.2  # 近5日均量 > 20日均量 1.2 倍 → 量增

# ── 各模組滿分 ────────────────────────────────────────────
MAX_REVENUE_SCORE   = 15
MAX_EPS_SCORE       = 15
MAX_PE_SCORE        = 10
MAX_ROE_SCORE       = 10
MAX_MA_SCORE        = 20
MAX_MOMENTUM_SCORE  = 15
MAX_VOLUME_SCORE    = 15

# ── MOPS 月營收 API ──────────────────────────────────────
MOPS_TWSE_URL = "https://mops.twse.com.tw/mops/web/ajax_t05st10_ifrs"
MOPS_OTC_URL  = "https://mops.twse.com.tw/mops/web/ajax_t05st31_ifrs"
MOPS_TIMEOUT  = 12

# ── FinMind 備援月營收 API ────────────────────────────────
FINMIND_URL     = "https://api.finmindtrade.com/api/v4/data"
FINMIND_TIMEOUT = 15

# ── 三大法人買賣超 API ────────────────────────────────────
TWSE_3INSTI_URL = "https://www.twse.com.tw/rwd/zh/fund/T86"
TPEX_3INSTI_URL = "https://www.tpex.org.tw/web/stock/3insti/daily_trade/3itrade_hedge_result.php"
INSTI_TIMEOUT   = 15

# ── 外資買賣超門檻（股數）────────────────────────────────
INSTI_FOREIGN_HIGH  = 5_000_000   # 外資大買 > 500 張
INSTI_FOREIGN_MED   =   500_000   # 外資中買 > 50 張
INSTI_TRUST_HIGH    =   500_000   # 投信大買 > 50 張
INSTI_TRUST_MED     =    50_000   # 投信中買 > 5 張

# ── 法人分析滿分 ──────────────────────────────────────────
MAX_INSTI_SCORE   = 20   # 各機構合計；中性基線 = 10，可加減 ±10
MAX_INSTI_FOREIGN = 12
MAX_INSTI_TRUST   =  5
MAX_INSTI_DEALER  =  3
