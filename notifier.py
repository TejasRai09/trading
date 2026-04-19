# -*- coding: utf-8 -*-
import sys, io
# Force UTF-8 output on Windows to avoid emoji encoding errors
if sys.stdout.encoding != 'utf-8':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')
"""
notifier.py  --  Send Telegram alerts when stocks pass the scanner filter.
"""

import requests
from datetime import datetime
from config import (
    TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID, 
    TELEGRAM_TIMEOUT, TELEGRAM_RETRY_COUNT, TELEGRAM_PROXY
)
import time


def send_telegram(message: str) -> bool:
    """Send a message to Telegram with retries and optional proxy."""
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id":    TELEGRAM_CHAT_ID,
        "text":       message,
        "parse_mode": "HTML",
    }
    
    proxies = None
    if TELEGRAM_PROXY:
        proxies = {
            "http":  TELEGRAM_PROXY,
            "https": TELEGRAM_PROXY,
        }

    for attempt in range(TELEGRAM_RETRY_COUNT):
        try:
            resp = requests.post(
                url, 
                json=payload, 
                timeout=TELEGRAM_TIMEOUT, 
                proxies=proxies
            )
            resp.raise_for_status()
            return True
        except Exception as e:
            wait = (attempt + 1) * 2  # Incremental backoff
            if attempt < TELEGRAM_RETRY_COUNT - 1:
                print(f"⚠️  Telegram retry {attempt + 1}/{TELEGRAM_RETRY_COUNT} due to: {e} (waiting {wait}s)")
                time.sleep(wait)
            else:
                print(f"❌ Telegram error after {TELEGRAM_RETRY_COUNT} attempts: {e}")
    
    return False


def format_stock_alert(result: dict) -> str:
    """Format a single stock result as a Telegram message."""
    symbol    = result.get("symbol", "?")
    ltp       = result.get("ltp", "?")
    vwap      = result.get("vwap", "?")
    chg       = result.get("daily_change_pct", "?")
    vol_ratio = result.get("volume_ratio", "?")
    rsi_10    = result.get("rsi_10min", "?")
    rsi_d     = result.get("rsi_daily", "?")
    t         = result.get("candle_time", "?")

    msg = (
        f"🟢 <b>{symbol}</b> — Intraday Scanner Alert\n"
        f"🕐 Candle: {t}\n"
        f"💰 LTP: ₹{ltp}  |  VWAP: ₹{vwap}\n"
        f"📈 Day Change: +{chg}%\n"
        f"📊 Volume: {vol_ratio}x avg\n"
        f"🔵 RSI(10m): {rsi_10}  |  RSI(daily): {rsi_d}\n"
        f"✅ All 10 conditions satisfied"
    )
    return msg


def send_scan_results(results: list[dict], scan_time: datetime = None) -> None:
    """Send all passing stocks as Telegram messages."""
    if scan_time is None:
        scan_time = datetime.now()

    time_str = scan_time.strftime("%I:%M %p")

    if not results:
        msg = (
            f"🔍 <b>Intraday Scanner</b> — {time_str}\n"
            f"No stocks passed all 10 conditions this scan."
        )
        send_telegram(msg)
        return

    # Header message
    header = (
        f"🔍 <b>Intraday Scanner</b> — {time_str}\n"
        f"📋 <b>{len(results)} stock(s) passed all conditions:</b>\n"
        + "─" * 30
    )
    send_telegram(header)

    # Individual stock messages
    for res in results:
        msg = format_stock_alert(res)
        send_telegram(msg)

    print(f"✅ Sent {len(results)} Telegram alerts.")


def test_telegram():
    """Quick test to verify Telegram credentials work."""
    ok = send_telegram("\u2705 <b>Stock Scanner</b> \u2014 Telegram connection test successful!")
    if ok:
        print("[OK] Telegram test message sent successfully!")
    else:
        print("[FAIL] Telegram test failed. Check BOT_TOKEN and CHAT_ID in config.py")


if __name__ == "__main__":
    test_telegram()
