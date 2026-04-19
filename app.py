"""
app.py  —  Streamlit Dashboard for the Intraday Stock Scanner

Run with:  streamlit run app.py
"""

import streamlit as st
import pandas as pd
import threading
import time
from datetime import datetime
import pytz

from instruments import load_instruments
from scanner     import run_full_scan
from notifier    import send_scan_results, test_telegram

# ── Page Config ───────────────────────────────────────────────────────────
st.set_page_config(
    page_title="Intraday Scanner",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Custom CSS ────────────────────────────────────────────────────────────
st.markdown("""
<style>
  @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&display=swap');

  html, body, [class*="css"] {
    font-family: 'Inter', sans-serif;
    background: #0d1117;
    color: #e6edf3;
  }

  .main-header {
    background: linear-gradient(135deg, #1a1f2e 0%, #16213e 100%);
    border: 1px solid #30363d;
    border-radius: 12px;
    padding: 1.5rem 2rem;
    margin-bottom: 2rem;
    text-align: center;
  }

  .main-header h1 {
    font-size: 2rem;
    font-weight: 700;
    background: linear-gradient(90deg, #00d4aa, #0096ff);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    margin: 0;
  }

  .main-header p {
    color: #8b949e;
    margin: 0.3rem 0 0 0;
    font-size: 0.9rem;
  }

  .metric-card {
    background: #161b22;
    border: 1px solid #30363d;
    border-radius: 10px;
    padding: 1rem 1.2rem;
    text-align: center;
  }

  .metric-card .value {
    font-size: 2rem;
    font-weight: 700;
    color: #00d4aa;
  }

  .metric-card .label {
    font-size: 0.8rem;
    color: #8b949e;
    margin-top: 0.2rem;
  }

  .stock-row-pass {
    background: rgba(0, 212, 170, 0.08);
    border-left: 3px solid #00d4aa;
    border-radius: 6px;
    padding: 0.8rem 1rem;
    margin-bottom: 0.5rem;
  }

  .stock-symbol {
    font-size: 1.2rem;
    font-weight: 700;
    color: #00d4aa;
  }

  .badge {
    display: inline-block;
    padding: 0.2rem 0.6rem;
    border-radius: 20px;
    font-size: 0.75rem;
    font-weight: 600;
    margin: 0.1rem;
  }

  .badge-green { background: rgba(0, 212, 170, 0.15); color: #00d4aa; }
  .badge-blue  { background: rgba(0, 150, 255, 0.15); color: #0096ff; }

  .status-live {
    display: inline-block;
    width: 8px; height: 8px;
    background: #00d4aa;
    border-radius: 50%;
    animation: pulse 1.5s infinite;
    margin-right: 6px;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50%       { opacity: 0.3; }
  }

  div[data-testid="stDataFrame"] { border-radius: 10px; }

  .stButton > button {
    background: linear-gradient(135deg, #00d4aa, #0096ff);
    color: #0d1117;
    font-weight: 700;
    border: none;
    border-radius: 8px;
    padding: 0.5rem 1.5rem;
    width: 100%;
  }

  .stButton > button:hover {
    opacity: 0.9;
    transform: translateY(-1px);
  }
</style>
""", unsafe_allow_html=True)

# ── IST time helper ───────────────────────────────────────────────────────
IST = pytz.timezone("Asia/Kolkata")

def now_ist():
    return datetime.now(IST)

# ── Session state init ────────────────────────────────────────────────────
if "scan_results"  not in st.session_state:  st.session_state.scan_results  = []
if "last_scan_time" not in st.session_state: st.session_state.last_scan_time = None
if "is_scanning"   not in st.session_state:  st.session_state.is_scanning   = False
if "scan_log"      not in st.session_state:  st.session_state.scan_log      = []
if "progress"      not in st.session_state:  st.session_state.progress      = (0, 0, "")

# ── Header ────────────────────────────────────────────────────────────────
st.markdown("""
<div class="main-header">
  <h1>📈 Intraday Stock Scanner</h1>
  <p>NSE Equity · Upstox Live Data · 10-Minute Candles · Chartink Filter Logic</p>
</div>
""", unsafe_allow_html=True)

# ── Sidebar ───────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### ⚙️ Controls")

    if st.button("🔍 Run Scan Now", key="btn_scan"):
        st.session_state.is_scanning   = True
        st.session_state.scan_results  = []
        st.session_state.scan_log      = []

    st.markdown("---")
    send_tg = st.checkbox("📲 Send Telegram Alerts", value=True)

    if st.button("✉️ Test Telegram", key="btn_tg"):
        test_telegram()
        st.success("Telegram test sent!")

    st.markdown("---")
    st.markdown("### 📋 Scanner Rules")
    st.markdown("""
    1. Daily change ≥ 2%
    2. 10min low ≤ VWAP
    3. Prev 10min close ≥ VWAP
    4. 10min RSI ≥ WMA(RSI,21)
    5. Daily RSI ≥ WMA(RSI,21)
    6. 10min vol > SMA(vol,20)
    7. All NSE Stocks (Universe)
    8. Monthly high > Monthly BB upper (Optional)
    9. Daily close > Monthly BB upper (Optional)
    10. 10min RSI ≥ max(5, RSI)
    """)

    st.markdown("---")
    t = now_ist()
    st.markdown(f"🕐 **IST Time:** {t.strftime('%I:%M:%S %p')}")

# ── Metrics row ───────────────────────────────────────────────────────────
col1, col2, col3, col4 = st.columns(4)

with col1:
    st.markdown(f"""
    <div class="metric-card">
      <div class="value">{len(st.session_state.scan_results)}</div>
      <div class="label">Stocks Passed</div>
    </div>""", unsafe_allow_html=True)

with col2:
    last = st.session_state.last_scan_time
    last_str = last.strftime("%I:%M %p") if last else "—"
    st.markdown(f"""
    <div class="metric-card">
      <div class="value" style="font-size:1.3rem">{last_str}</div>
      <div class="label">Last Scan</div>
    </div>""", unsafe_allow_html=True)

with col3:
    cur, tot, sym = st.session_state.progress
    prog_str = f"{cur}/{tot}" if tot > 0 else "—"
    st.markdown(f"""
    <div class="metric-card">
      <div class="value" style="font-size:1.3rem">{prog_str}</div>
      <div class="label">Progress</div>
    </div>""", unsafe_allow_html=True)

with col4:
    is_live = "<span class='status-live'></span>LIVE" if st.session_state.is_scanning else "IDLE"
    color   = "#00d4aa" if st.session_state.is_scanning else "#8b949e"
    st.markdown(f"""
    <div class="metric-card">
      <div class="value" style="font-size:1.3rem; color:{color}">{is_live}</div>
      <div class="label">Scanner Status</div>
    </div>""", unsafe_allow_html=True)

st.markdown("<br>", unsafe_allow_html=True)

# ── Run scan if triggered ─────────────────────────────────────────────────
if st.session_state.is_scanning:
    instruments = load_instruments()
    progress_bar = st.progress(0, text="Loading instruments...")
    log_area     = st.empty()

    def progress_cb(cur, tot, sym):
        st.session_state.progress = (cur, tot, sym)
        pct = int(cur / tot * 100)
        progress_bar.progress(pct, text=f"Scanning {sym} ({cur}/{tot})...")

    results = run_full_scan(instruments, progress_callback=progress_cb)

    st.session_state.scan_results   = results
    st.session_state.last_scan_time = now_ist()
    st.session_state.is_scanning    = False
    st.session_state.progress       = (0, 0, "")

    if send_tg:
        send_scan_results(results, scan_time=st.session_state.last_scan_time)

    progress_bar.empty()
    st.rerun()

# ── Results Table ─────────────────────────────────────────────────────────
st.markdown("### 📊 Scan Results")

if not st.session_state.scan_results:
    st.info("No results yet. Click **Run Scan Now** in the sidebar to start.")
else:
    results = st.session_state.scan_results

    # Build display DataFrame
    rows = []
    for r in results:
        rows.append({
            "Symbol":         r.get("symbol"),
            "LTP (₹)":        r.get("ltp"),
            "VWAP (₹)":       r.get("vwap"),
            "Day Chg %":      r.get("daily_change_pct"),
            "Vol Ratio":      r.get("volume_ratio"),
            "RSI (10m)":      r.get("rsi_10min"),
            "RSI (Daily)":    r.get("rsi_daily"),
            "Daily Close":    r.get("daily_close"),
            "Monthly BB Up":  r.get("monthly_bb_upper"),
            "Candle Time":    r.get("candle_time"),
        })

    df_display = pd.DataFrame(rows)
    st.dataframe(
        df_display.style
            .format({
                "Day Chg %":  "+{:.2f}%",
                "Vol Ratio":  "{:.2f}x",
                "RSI (10m)":  "{:.2f}",
                "RSI (Daily)":"{:.2f}",
            })
            .background_gradient(subset=["Day Chg %"], cmap="Greens")
            .background_gradient(subset=["Vol Ratio"],  cmap="Blues"),
        use_container_width=True,
        height=400,
    )

    # Download button
    csv = df_display.to_csv(index=False)
    st.download_button(
        label="⬇️ Download CSV",
        data=csv,
        file_name=f"scan_{now_ist().strftime('%Y%m%d_%H%M')}.csv",
        mime="text/csv",
    )

# ── Auto-refresh note ─────────────────────────────────────────────────────
st.markdown("---")
st.caption("💡 Tip: Refresh the page or re-click 'Run Scan Now' every 10 minutes at 9:25, 9:35, 9:45... for live intraday signals.")
