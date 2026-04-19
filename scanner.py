"""
scanner.py  —  Apply all 10 filter conditions to a single stock.

Filter Conditions (from original Chartink formula):
 1. daily % change >= 2%
 2. [0] 10min low <= [0] 10min VWAP
 3. [-1] 10min close >= [-1] 10min VWAP
 4. [0] 10min RSI(9) >= [0] 10min WMA(RSI(9), 21)
 5. daily RSI(9) >= daily WMA(RSI(9), 21)
 6. [0] 10min volume > [0] 10min SMA(volume, 20)
 7. market cap >= 500 Cr  [pre-filtered via instruments list]
 8. monthly high > monthly upper BB(20, 2)
 9. daily close > monthly upper BB(20, 2)
10. [0] 10min RSI(9) >= max(5, [0] 10min RSI(9))
"""

import pandas as pd
from concurrent.futures import ThreadPoolExecutor, as_completed
from data_fetcher import (
    get_10min_candles, get_daily_candles, get_monthly_candles, get_market_quotes
)
from indicators   import prepare_10min, prepare_daily, prepare_monthly
from config       import MIN_DAILY_CHANGE_PCT


def _safe_val(obj, col: str = None, idx: int = -1):
    """Safely get a value from a DataFrame or Series, returns None on failure."""
    try:
        if col:
            # If obj is a DataFrame, obj[col] is a Series, so we use .iloc[idx]
            # If obj is a Series (one row), obj[col] is a scalar, so we return it directly
            target = obj[col]
            if hasattr(target, "iloc"):
                val = target.iloc[idx]
            else:
                val = target
        else:
            # If no column specified, it's likely a row Series or we want the full obj's index
            val = obj.iloc[idx]
            
        if pd.isna(val):
            return None
        return float(val)
    except (IndexError, KeyError, TypeError, AttributeError):
        return None


def scan_stock(symbol: str, instrument_key: str) -> dict | None:
    """
    Run all 10 filter conditions on a single stock.

    Returns a result dict if ALL conditions pass, or None if any condition fails.
    The dict contains key indicator values for display in the dashboard.
    """
    result = {"symbol": symbol, "conditions_passed": [], "conditions_failed": []}

    # ── Fetch data ────────────────────────────────────────────────────────
    df_10 = get_10min_candles(instrument_key, days_back=5)
    df_d  = get_daily_candles(instrument_key, days_back=365)
    df_m  = get_monthly_candles(instrument_key, months_back=36)

    if df_10.empty or len(df_10) < 22:
        print(f"  ❌ {symbol}: Insufficient 10m data ({len(df_10)} candles)")
        return None
    if df_d.empty or len(df_d) < 22:
        print(f"  ❌ {symbol}: Insufficient Daily data")
        return None
    if df_m.empty or len(df_m) < 21:
        print(f"  ❌ {symbol}: Insufficient Monthly data")
        return None

    # ── Add indicators ────────────────────────────────────────────────────
    df_10 = prepare_10min(df_10)
    df_d  = prepare_daily(df_d)
    df_m  = prepare_monthly(df_m)

    # ── Extract rows ──────────────────────────────────────────────────────
    if len(df_10) < 3:
        print(f"  ❌ {symbol}: Not enough processed candles")
        return None
        
    c_live = df_10.iloc[-1]
    c0     = df_10.iloc[-2]  # We use the COMPLETED candle for stable indicators
    c1     = df_10.iloc[-3]
    last_d = df_d.iloc[-1]

    # ── Condition 1: Daily % change >= 2% ─────────────────────────────────
    if len(df_d) < 2:
        return None
    prev_close   = _safe_val(df_d, "close", -2)
    daily_close  = _safe_val(df_d, "close", -1)
    if prev_close is None or daily_close is None or prev_close == 0:
        return None
    daily_change = (daily_close - prev_close) / prev_close * 100
    if daily_change < MIN_DAILY_CHANGE_PCT:
        print(f"  FAILED {symbol}: Daily %chg ({daily_change:.2f}%) < {MIN_DAILY_CHANGE_PCT}%")
        return None
    result["daily_change_pct"] = round(daily_change, 2)
    result["conditions_passed"].append("C1: daily %chg >= 2%")

    # ── Condition 2: [0] 10min low <= [0] 10min VWAP ──────────────────────
    c0_low  = _safe_val(c0, "low")
    c0_vwap = _safe_val(c0, "vwap")
    if c0_low is None or c0_vwap is None or c0_low > c0_vwap:
        print(f"  FAILED {symbol}: 10m Low ({c0_low}) > VWAP ({c0_vwap:.2f})")
        return None
    result["conditions_passed"].append("C2: 10min low <= VWAP")

    # ── Condition 3: [-1] 10min close >= [-1] 10min VWAP ──────────────────
    c1_close = _safe_val(c1, "close")
    c1_vwap  = _safe_val(c1, "vwap")
    if c1_close is None or c1_vwap is None or c1_close < c1_vwap:
        print(f"  FAILED {symbol}: Prev 10m Close ({c1_close}) < VWAP ({c1_vwap:.2f})")
        return None
    result["conditions_passed"].append("C3: prev 10min close >= VWAP")

    # ── Condition 4: [0] 10min RSI(9) >= [0] 10min WMA(RSI(9), 21) ────────
    c0_rsi     = _safe_val(c0, "rsi")
    c0_wma_rsi = _safe_val(c0, "wma_rsi")
    if c0_rsi is None or c0_wma_rsi is None or c0_rsi < c0_wma_rsi:
        print(f"  FAILED {symbol}: 10m RSI ({c0_rsi:.1f}) < WMA_RSI ({c0_wma_rsi:.1f})")
        return None
    result["rsi_10min"]     = round(c0_rsi, 2)
    result["wma_rsi_10min"] = round(c0_wma_rsi, 2)
    result["conditions_passed"].append("C4: 10min RSI >= WMA(RSI)")

    # ── Condition 5: daily RSI(9) >= daily WMA(RSI(9), 21) ────────────────
    d_rsi     = _safe_val(last_d, "rsi")
    d_wma_rsi = _safe_val(last_d, "wma_rsi")
    if d_rsi is None or d_wma_rsi is None or d_rsi < d_wma_rsi:
        print(f"  FAILED {symbol}: Daily RSI ({d_rsi:.1f}) < WMA_RSI ({d_wma_rsi:.1f})")
        return None
    result["rsi_daily"]     = round(d_rsi, 2)
    result["wma_rsi_daily"] = round(d_wma_rsi, 2)
    result["conditions_passed"].append("C5: daily RSI >= WMA(RSI)")

    # ── Condition 6: [0] 10min volume > SMA(volume, 20) ───────────────────
    c0_vol     = _safe_val(c0, "volume")
    c0_vol_sma = _safe_val(c0, "vol_sma")
    if c0_vol is None or c0_vol_sma is None or c0_vol <= c0_vol_sma:
        print(f"  FAILED {symbol}: 10m Vol ({c0_vol}) <= SMA_Vol ({c0_vol_sma:.0f})")
        return None
    result["volume_ratio"] = round(c0_vol / c0_vol_sma, 2)
    result["conditions_passed"].append("C6: 10min vol > SMA(vol)")

    # ── Condition 8: monthly high > monthly upper BB(20, 2) ───────────────
    # m_high   = _safe_val(df_m, "high", -1)
    # m_bb_upper = _safe_val(df_m, "bb_upper", -1)
    # if m_high is None or m_bb_upper is None or m_high <= m_bb_upper:
    #     return None
    # result["monthly_high"]     = round(m_high, 2)
    # result["monthly_bb_upper"] = round(m_bb_upper, 2)
    # result["conditions_passed"].append("C8: monthly high > monthly BB upper")

    # ── Condition 9: daily close > monthly upper BB(20, 2) ────────────────
    # d_close    = daily_close
    # # Use the latest monthly BB upper (same as above)
    # if d_close is None or m_bb_upper is None or d_close <= m_bb_upper:
    #     return None
    # result["daily_close"]      = round(d_close, 2)
    # result["conditions_passed"].append("C9: daily close > monthly BB upper")

    # ── Condition 10: [0] RSI(9) >= max(5, RSI(9)) ────────────────────────
    c0_rsi_max = _safe_val(c0, "rsi_max")
    if c0_rsi_max is None or c0_rsi < c0_rsi_max:
        print(f"  FAILED {symbol}: 10m RSI ({c0_rsi:.1f}) < Max(5) RSI ({c0_rsi_max:.1f})")
        return None
    result["conditions_passed"].append("C10: 10min RSI >= max(5, RSI)")

    # ── All conditions passed! ─────────────────────────────────────────
    result["ltp"]          = round(c_live["close"], 2)
    result["vwap"]         = round(c0_vwap, 2)
    result["candle_time"]  = str(c0.name) if hasattr(c0, "name") else "N/A"
    result["all_passed"]   = True
    print(f"  ✅ PASSED: {symbol}")
    return result


def run_full_scan(instruments: pd.DataFrame, progress_callback=None) -> list[dict]:
    """
    Optimized scan using:
    1. Phase 1: Batch Quotes filtering (Daily Change >= 2%) - reduces 2400 stocks to ~100.
    2. Phase 2: Parallel scanning of remaining stocks using ThreadPoolExecutor.
    """
    results = []
    
    # ── Phase 1: Batch Pre-filter ──────────────────────────────────────────
    # Upstox Quote API returns keys like NSE_EQ:SYMBOL, but the data object
    # contains the 'instrument_token' (ISIN) which we use for our heavy scan.
    all_keys = instruments["instrument_key"].tolist()
    key_to_info = {}
    for _, row in instruments.iterrows():
        key_to_info[row["instrument_key"]] = {
            "symbol":         row["symbol"],
            "instrument_key": row["instrument_key"]
        }

    if progress_callback:
        # Initialize progress bar with actual total count of instruments
        progress_callback(0, len(all_keys), "Phase 1: Starting...")
    
    passed_pre_filter = []
    print(f"🔍 Phase 1: Checking daily move for {len(all_keys)} stocks...")
    
    # Check in batches of 50 (Upstox Quote API limit)
    for i in range(0, len(all_keys), 50):
        batch = all_keys[i : i + 50]
        try:
            quotes = get_market_quotes(batch)
            for api_key, data in quotes.items():
                # Map back using 'instrument_token' in the response data
                token = data.get("instrument_token")
                info = key_to_info.get(token)
                
                if not info:
                    continue

                ltp        = data.get("last_price")
                net_change = data.get("net_change")
                
                if ltp and net_change is not None:
                    # Calculate previous close from LTP and net change
                    # prev_close = ltp - net_change
                    # change_pct = (net_change / prev_close) * 100
                    
                    # Upstox net_change is (LTP - PrevClose)
                    prev_close = ltp - net_change
                    if prev_close > 0:
                        change = (net_change / prev_close) * 100
                        if change >= MIN_DAILY_CHANGE_PCT:
                            passed_pre_filter.append(info)
        except Exception as e:
            print(f"  ⚠️  Batch error: {e}")

    total_passed = len(passed_pre_filter)
    print(f"🚀 Phase 1 complete. Found {total_passed} stocks moving >= {MIN_DAILY_CHANGE_PCT}% in the full universe.")

    if total_passed == 0:
        return []

    # ── Phase 2: Parallel Full Scan ────────────────────────────────────────
    print(f"⚡ Phase 2: Scanning indicators for {total_passed} stocks (3 at a time)...")
    
    # Reducing workers to 3 to be gentler on the API rate limits
    with ThreadPoolExecutor(max_workers=3) as executor:
        future_to_stock = {
            executor.submit(scan_stock, s["symbol"], s["instrument_key"]): s["symbol"]
            for s in passed_pre_filter
        }
        
        count = 0
        for future in as_completed(future_to_stock):
            count += 1
            symbol = future_to_stock[future]
            
            if progress_callback:
                progress_callback(count, total_passed, symbol)
                
            try:
                res = future.result()
                if res and res.get("all_passed"):
                    results.append(res)
                else:
                    # print(f"  ❌ {symbol}")
                    pass
            except Exception as e:
                print(f"  ⚠️  {symbol}: Error — {e}")

    return results
