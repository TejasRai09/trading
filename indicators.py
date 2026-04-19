"""
indicators.py  —  Pure-pandas technical indicator calculations.
                   No pandas-ta / numba dependency (compatible with Python 3.14).

Indicators Required:
  [10-min timeframe]  VWAP, RSI(9), WMA(RSI,21), SMA(volume,20), Max(RSI,5)
  [Daily timeframe]   RSI(9), WMA(RSI,21), Bollinger Band Upper(20,2)
  [Monthly timeframe] Bollinger Band Upper(20,2), Monthly High
"""

import pandas as pd
import numpy as np
from config import RSI_PERIOD, WMA_PERIOD, BB_PERIOD, BB_STD, VOL_SMA_PERIOD, RSI_MAX_LOOKBACK


# ── RSI (Wilder's Smoothing) ──────────────────────────────────────────────

def calc_rsi(series: pd.Series, period: int = RSI_PERIOD) -> pd.Series:
    """Wilder's RSI — same as Chartink / TradingView."""
    delta = series.diff()
    gain  = delta.clip(lower=0)
    loss  = (-delta).clip(lower=0)

    # First average
    avg_gain = gain.rolling(window=period, min_periods=period).mean()
    avg_loss = loss.rolling(window=period, min_periods=period).mean()

    # Wilder's smoothing (EWM with com = period-1)
    avg_gain = gain.ewm(com=period - 1, min_periods=period, adjust=False).mean()
    avg_loss = loss.ewm(com=period - 1, min_periods=period, adjust=False).mean()

    rs  = avg_gain / avg_loss.replace(0, np.nan)
    rsi = 100 - (100 / (1 + rs))
    return rsi


# ── WMA (Weighted Moving Average) ────────────────────────────────────────

def calc_wma(series: pd.Series, period: int = WMA_PERIOD) -> pd.Series:
    """Linearly-weighted moving average."""
    weights = np.arange(1, period + 1, dtype=float)
    return series.rolling(window=period).apply(
        lambda x: np.dot(x, weights) / weights.sum(), raw=True
    )


# ── SMA ───────────────────────────────────────────────────────────────────

def calc_sma(series: pd.Series, period: int) -> pd.Series:
    return series.rolling(window=period).mean()


# ── Bollinger Band Upper ──────────────────────────────────────────────────

def calc_bb_upper(series: pd.Series, period: int = BB_PERIOD, std: float = BB_STD) -> pd.Series:
    mid = series.rolling(window=period).mean()
    std_dev = series.rolling(window=period).std(ddof=0)
    return mid + std * std_dev


# ── VWAP (Daily-anchored) ────────────────────────────────────────────────

def calc_vwap_daily_anchored(df: pd.DataFrame) -> pd.Series:
    """
    VWAP resets each trading day.
    Requires: open, high, low, close, volume in df.
    """
    df = df.copy()
    df["tp"]   = (df["high"] + df["low"] + df["close"]) / 3
    df["tpv"]  = df["tp"] * df["volume"]
    df["date"] = df.index.normalize()  # date-only

    groups = df.groupby("date")
    cum_tpv = groups["tpv"].cumsum()
    cum_vol = groups["volume"].cumsum()

    vwap = cum_tpv / cum_vol.replace(0, np.nan)
    return vwap


# ── All-in-one builders ───────────────────────────────────────────────────

def prepare_10min(df: pd.DataFrame) -> pd.DataFrame:
    """Add VWAP, RSI, WMA(RSI), SMA(vol), RSI-max to a 10-min DataFrame."""
    df = df.copy()
    df["vwap"]    = calc_vwap_daily_anchored(df)
    df["rsi"]     = calc_rsi(df["close"], RSI_PERIOD)
    df["wma_rsi"] = calc_wma(df["rsi"], WMA_PERIOD)
    df["vol_sma"] = calc_sma(df["volume"], VOL_SMA_PERIOD)
    df["rsi_max"] = df["rsi"].rolling(window=RSI_MAX_LOOKBACK).max()
    return df


def prepare_daily(df: pd.DataFrame) -> pd.DataFrame:
    """Add RSI, WMA(RSI), BB upper to a daily DataFrame."""
    df = df.copy()
    df["rsi"]      = calc_rsi(df["close"], RSI_PERIOD)
    df["wma_rsi"]  = calc_wma(df["rsi"], WMA_PERIOD)
    df["bb_upper"] = calc_bb_upper(df["close"], BB_PERIOD, BB_STD)
    return df


def prepare_monthly(df: pd.DataFrame) -> pd.DataFrame:
    """Add BB upper to a monthly DataFrame."""
    df = df.copy()
    df["bb_upper"] = calc_bb_upper(df["close"], BB_PERIOD, BB_STD)
    return df
