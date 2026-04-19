"""
instruments.py  —  Download and manage the NSE instrument list.

Upstox provides a JSON file with all NSE instruments.
We download it once per day, extract Cash segment equities,
and filter by the NIFTY 500 list to ensure we scan the most liquid stocks quickly.
"""

import os
import json
import gzip
import requests
import pandas as pd
import sys
import io
from datetime import datetime, date
from config import SCAN_NIFTY_500_ONLY

# Force UTF-8 output on Windows to avoid emoji encoding errors
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

INSTRUMENTS_FILE  = "instruments_nse.csv"
INSTRUMENTS_URL   = "https://assets.upstox.com/market-quote/instruments/exchange/NSE.json.gz"
NIFTY_500_URL     = "https://archives.nseindia.com/content/indices/ind_nifty500list.csv"

# Headers to bypass NSE's basic bot protection
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Accept": "*/*",
}

def get_nifty_500_symbols() -> list[str]:
    """Download the current NIFTY 500 list from NSE archives."""
    try:
        print("🔍 Fetching NIFTY 500 list from NSE...")
        resp = requests.get(NIFTY_500_URL, headers=NSE_HEADERS, timeout=15)
        resp.raise_for_status()
        
        # The CSV has a 'Symbol' column
        from io import StringIO
        df_500 = pd.read_csv(StringIO(resp.text))
        symbols = df_500['Symbol'].tolist()
        print(f"✅ Found {len(symbols)} stocks in NIFTY 500.")
        return symbols
    except Exception as e:
        print(f"⚠️  Could not fetch NIFTY 500 list: {e}")
        print("ℹ️  Falling back to scanning all NSE equities (or check your internet connection).")
        return []

def download_instruments(force: bool = False) -> pd.DataFrame:
    """Download the Upstox NSE instrument JSON file and cache it as CSV."""
    today = date.today().strftime("%Y-%m-%d")

    # Use cached file if it's from today
    if os.path.exists(INSTRUMENTS_FILE) and not force:
        try:
            df = pd.read_csv(INSTRUMENTS_FILE)
            if "download_date" in df.columns and df["download_date"].iloc[0] == today:
                print(f"📋 Loaded {len(df)} instruments from cache.")
                return df
        except Exception:
            pass

    print("⬇️  Downloading NSE instrument list from Upstox...")
    resp = requests.get(INSTRUMENTS_URL, timeout=30)
    resp.raise_for_status()

    # The file is gzip-compressed JSON
    data = json.loads(gzip.decompress(resp.content).decode("utf-8"))
    df = pd.DataFrame(data)

    # Keep only NSE EQ (Cash/Equity segment)
    df = df[df["segment"] == "NSE_EQ"].copy()
    df = df[df["instrument_type"] == "EQ"].copy()

    # Rename columns for clarity
    df = df.rename(columns={
        "instrument_key": "instrument_key",
        "trading_symbol": "symbol",
        "name":           "name",
        "lot_size":       "lot_size",
        "exchange":       "exchange",
    })

    df["download_date"] = today
    df.to_csv(INSTRUMENTS_FILE, index=False)
    print(f"✅ Saved {len(df)} NSE equity instruments to {INSTRUMENTS_FILE}")
    return df


def load_instruments() -> pd.DataFrame:
    """Load instruments, optionally filtered by NIFTY 500."""
    df = download_instruments()
    
    if SCAN_NIFTY_500_ONLY:
        # Get Nifty 500 symbols
        nifty_500 = get_nifty_500_symbols()
        
        if nifty_500:
            # Filter the universe
            df_filtered = df[df["symbol"].isin(nifty_500)].copy()
            
            if df_filtered.empty:
                print("⚠️  Warning: NIFTY 500 filter resulted in 0 stocks. Scanning all.")
                return df[["instrument_key", "symbol", "name"]].reset_index(drop=True)
                
            print(f"🚀 Pre-filtered to {len(df_filtered)} NIFTY 500 stocks for speed.")
            return df_filtered[["instrument_key", "symbol", "name"]].reset_index(drop=True)
            
    # Default: Return everything if flag is False or Nifty 500 fetch failed
    print(f"ℹ️  Scanning all {len(df)} NSE equity instruments.")
    return df[["instrument_key", "symbol", "name"]].reset_index(drop=True)


def get_instrument_key(symbol: str) -> str | None:
    """Return the Upstox instrument key for a given NSE symbol."""
    df = load_instruments()
    row = df[df["symbol"] == symbol.upper()]
    if row.empty:
        return None
    return row.iloc[0]["instrument_key"]


if __name__ == "__main__":
    df = load_instruments()
    print(df.head(10))
