import pandas as pd
import sys
import os
from scanner import scan_stock, run_full_scan, get_market_quotes, MIN_DAILY_CHANGE_PCT
from instruments import load_instruments

def diagnose():
    print("Loading instruments...")
    inst = load_instruments()
    
    print("Running Phase 1 (Batch Quote Pre-filter)...")
    all_keys = inst["instrument_key"].tolist()
    key_to_info = {row["instrument_key"]: {"symbol": row["symbol"], "instrument_key": row["instrument_key"]} for _, row in inst.iterrows()}
    
    candidates = []
    for i in range(0, len(all_keys), 50):
        batch = all_keys[i : i + 50]
        try:
            quotes = get_market_quotes(batch)
            for api_key, data in quotes.items():
                token = data.get("instrument_token")
                info = key_to_info.get(token)
                if not info: continue
                ltp = data.get("last_price")
                net_change = data.get("net_change")
                if ltp and net_change is not None:
                    prev_close = ltp - net_change
                    if prev_close > 0:
                        change = (net_change / prev_close) * 100
                        if change >= MIN_DAILY_CHANGE_PCT:
                            candidates.append(info)
        except Exception as e:
            print(f"Batch error: {e}")
    
    print(f"Phase 1 found {len(candidates)} candidates.")
    
    if not candidates:
        print("No candidates found in Phase 1.")
        return

    # Check first 5 candidates in depth
    for s in candidates[:5]:
        print(f"\n🔍 Diagnosing {s['symbol']} ({s['instrument_key']})...")
        try:
            from data_fetcher import get_10min_candles, get_daily_candles, get_monthly_candles
            from indicators import prepare_10min, prepare_daily, prepare_monthly
            from scanner import _safe_val
            
            # Fetch and prepare
            df_10 = get_10min_candles(s['instrument_key'], days_back=5)
            df_d  = get_daily_candles(s['instrument_key'], days_back=365)
            df_m  = get_monthly_candles(s['instrument_key'], months_back=36)
            
            print(f"  Data sizes: 10m={len(df_10)}, Daily={len(df_d)}, Monthly={len(df_m)}")
            
            if len(df_10) < 22: print("  ❌ Failed: Not enough 10m data (< 22)"); continue
            
            df_10 = prepare_10min(df_10)
            df_d  = prepare_daily(df_d)
            df_m  = prepare_monthly(df_m)
            
            c0 = df_10.iloc[-1]
            c1 = df_10.iloc[-2]
            last_d = df_d.iloc[-1]
            
            # Condition 2
            c0_low, c0_vwap = _safe_val(c0, "low"), _safe_val(c0, "vwap")
            print(f"  C2: Low={c0_low}, VWAP={c0_vwap} | Status={'PASS' if c0_low <= c0_vwap else 'FAIL'}")
            
            # Condition 3
            c1_close, c1_vwap = _safe_val(c1, "close"), _safe_val(c1, "vwap")
            print(f"  C3: Prev Close={c1_close}, Prev VWAP={c1_vwap} | Status={'PASS' if c1_close >= c1_vwap else 'FAIL'}")
            
            # Condition 4
            c0_rsi, c0_wma_rsi = _safe_val(c0, "rsi"), _safe_val(c0, "wma_rsi")
            print(f"  C4: 10m RSI={c0_rsi:.2f}, WMA_RSI={c0_wma_rsi:.2f} | Status={'PASS' if c0_rsi >= (c0_wma_rsi or 0) else 'FAIL'}")
            
            # Condition 5
            d_rsi, d_wma_rsi = _safe_val(last_d, "rsi"), _safe_val(last_d, "wma_rsi")
            print(f"  C5: Daily RSI={d_rsi:.2f}, WMA_RSI={d_wma_rsi:.2f} | Status={'PASS' if d_rsi >= (d_wma_rsi or 0) else 'FAIL'}")
            
            # Condition 6
            c0_vol, c0_vol_sma = _safe_val(c0, "volume"), _safe_val(c0, "vol_sma")
            print(f"  C6: Vol={c0_vol}, SMA_Vol={c0_vol_sma:.2f} | Status={'PASS' if c0_vol > (c0_vol_sma or 0) else 'FAIL'}")
            
            # Condition 10
            c0_rsi_max = _safe_val(c0, "rsi_max")
            print(f"  C10: RSI={c0_rsi:.2f}, Max(5)RSI={c0_rsi_max:.2f} | Status={'PASS' if c0_rsi >= (c0_rsi_max or 0) else 'FAIL'}")
            
        except Exception as e:
            print(f"  ⚠️ Error diagnosing {s['symbol']}: {e}")

if __name__ == "__main__":
    diagnose()
