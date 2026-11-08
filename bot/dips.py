"""Crypto dip scan on 5-minute bars: short-term uptrend (above EMA50) with a sharp pullback
(RSI(2) low). Entry at market, stop 2 ATR below, a near target (1.5 ATR) for a high hit rate.
Backtest 28.10.-4.11. (scripts/backtest_crypto_dips.py): slightly negative after costs."""
from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd
import yfinance as yf

from .intraday import CRYPTO
from .scanner import _px


def _rsi(c, n=2):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def scan(rsi_max=10, stop_atr=2.0, target_atr=1.5, short=False, symbols=None, trend_rsi=40, trend_gap_pct=0.3,
         min_stop_pct=0.6):
    now = datetime.now(timezone.utc)
    rows = []
    for sym in symbols or CRYPTO:
        df = yf.Ticker(sym).history(period="2d", interval="5m", prepost=False).dropna()
        df = df[df.index + timedelta(minutes=5) <= now]
        if len(df) < 60:
            continue
        c = df["Close"]
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(),
                        (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean().iloc[-1]
        ema50, r2, close = c.ewm(span=50).mean().iloc[-1], _rsi(c).iloc[-1], c.iloc[-1]
        # Long: dip in a short-term uptrend. Short (mirror): pop in a short-term downtrend.
        # In a strong trend (price trend_gap_pct away from the EMA) a smaller pullback is enough.
        gap = (close / ema50 - 1) * 100
        long_lim = trend_rsi if gap >= trend_gap_pct else rsi_max
        short_lim = trend_rsi if gap <= -trend_gap_pct else rsi_max
        if close > ema50 and r2 < long_lim:
            side, sign, extreme = "long", 1, r2
        elif short and close < ema50 and r2 > 100 - short_lim:
            side, sign, extreme = "short", -1, 100 - r2
        else:
            continue
        # Stops closer than min_stop_pct get shaken out by noise and lose a big share of R to costs
        # (SOL 4.11.: 0.34 % stop, out after 3 minutes, -1.26 R). So the stop is at least that far.
        dist = max(stop_atr * atr, close * min_stop_pct / 100)
        rows.append({"symbol": sym, "side": side, "close": _px(close), "stop": _px(close - sign * dist),
                     # The target scales with the (possibly widened) stop, so reward/risk stays >= 3.
                     "target": _px(close + sign * max(target_atr * atr, 3 * dist)), "rsi2": round(float(r2), 1),
                     "extreme": round(float(extreme), 1), "atr_pct": round(float(atr / close * 100), 2)})
    rows.sort(key=lambda r: r["extreme"])
    return rows
