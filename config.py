# ============================================================
#  config.py  —  All credentials and constants go here
#  Fill in your Upstox API Key and Secret after registering
#  at https://developer.upstox.com
# ============================================================

# ── Upstox OAuth2 ──────────────────────────────────────────
UPSTOX_API_KEY     = "63ab824b-1086-4adf-b3ab-cc08e93f5332"       # paste after Step 4
UPSTOX_API_SECRET  = "5wv21uf0z3"    # paste after Step 4
UPSTOX_REDIRECT_URI = "http://127.0.0.1:5000/callback"  # must match what you set in Upstox app

# Access token is fetched daily at run-time.
# The auth flow saves it to token.txt automatically.
TOKEN_FILE = "token.txt"

# -- Telegram ────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN = "8787170403:AAEmm26hWONTm51H5fgRqLo9U5OGQTtuovU"
TELEGRAM_CHAT_ID   = "-5268589886"
TELEGRAM_TIMEOUT   = 20
TELEGRAM_RETRY_COUNT = 3
TELEGRAM_PROXY     = None  # Example: "http://127.0.0.1:1080"

# ── Scanner Settings ────────────────────────────────────────
SCAN_NIFTY_500_ONLY = False    # Set to True for faster Nifty 500 scans
MARKET_OPEN     = "09:15"
FIRST_SCAN_TIME = "09:25"   # first COMPLETE 10-min candle ends at 9:25
SCAN_INTERVAL_MIN = 10      # re-scan every 10 minutes

# ── Filter Thresholds ───────────────────────────────────────
MIN_DAILY_CHANGE_PCT = 2.0   # daily % change >= 2%
MIN_MARKET_CAP_CR    = 500   # market cap >= ₹500 Cr (pre-filter via stock list)

# ── Indicator Periods ───────────────────────────────────────
RSI_PERIOD         = 9
WMA_PERIOD         = 21
BB_PERIOD          = 20
BB_STD             = 2
VOL_SMA_PERIOD     = 20
RSI_MAX_LOOKBACK   = 5       # RSI must be >= max of last 5 RSI values
