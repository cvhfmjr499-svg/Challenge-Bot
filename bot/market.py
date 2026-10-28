"""Market data via yfinance (free, no API key)."""
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


def intraday_bars(symbols, since: datetime):
    """5-minute regular-session bars from `since` (yfinance keeps ~60 days)."""
    start = max(since, datetime.now(since.tzinfo) - timedelta(days=55))
    out = {}
    for sym in symbols:
        df = yf.Ticker(sym).history(start=start.date(), interval="5m", prepost=False,
                                    auto_adjust=False)
        if not df.empty:
            out[sym] = df[["Open", "High", "Low", "Close"]].dropna()
    return out


def last_price(symbol):
    df = yf.Ticker(symbol).history(period="5d", interval="5m", prepost=False)
    if df.empty:
        raise ValueError(f"Keine Kursdaten für {symbol}.")
    return float(df["Close"].iloc[-1])


def daily_bars(symbols, period="1y"):
    df = yf.download(symbols, period=period, interval="1d", group_by="ticker",
                     auto_adjust=True, progress=False, threads=True)
    out = {}
    for sym in symbols:
        try:
            d = df[sym] if isinstance(df.columns, pd.MultiIndex) else df
        except KeyError:
            continue
        d = d.dropna()
        if len(d) > 0:
            out[sym] = d
    return out
