"""Market data via yfinance (free, no API key)."""
from datetime import datetime, timedelta

import pandas as pd
import yfinance as yf


def intraday_bars(symbols, since: datetime):
    """Regular-session bars from `since`: 1-minute when yfinance still has them (7 days),
    otherwise 5-minute (~60 days). Each frame carries its bar length in `attrs["bar"]`."""
    now = datetime.now(since.tzinfo)
    if now - since < timedelta(days=6, hours=12):
        interval, bar, start = "1m", timedelta(minutes=1), since
    else:
        interval, bar, start = "5m", timedelta(minutes=5), max(since, now - timedelta(days=55))
    out = {}
    for sym in symbols:
        df = yf.Ticker(sym).history(start=start.date(), interval=interval, prepost=False,
                                    auto_adjust=False)
        if not df.empty:
            df = df[["Open", "High", "Low", "Close"]].dropna()
            df.attrs["bar"] = bar
            out[sym] = df
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
