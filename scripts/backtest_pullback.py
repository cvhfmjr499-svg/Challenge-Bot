"""Backtest: buy short pullbacks in long-term uptrends (daily bars), with Kraken costs.

Entry  : close > SMA200 and RSI(2) < threshold -> buy at the next day's open.
Exit   : first close above SMA5 (sell at that close), or the stop (entry - k * ATR14), or after
         max_days. Costs: 0.04 % spread per side. Results in R (R = entry - stop).
Usage  : python3 scripts/backtest_pullback.py
"""
import sys

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from bot.scanner import CRYPTO_UNIVERSE, UNIVERSE  # noqa: E402

SPREAD = 0.0004


def rsi(close, n=2):
    d = close.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    down = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / down.replace(0, np.nan))


def trades_for(sym, df, rsi_max, k_atr, max_days):
    c = df["Close"]
    sma200, sma5 = c.rolling(200).mean(), c.rolling(5).mean()
    tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(), (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
    atr = tr.rolling(14).mean()
    r2 = rsi(c)
    out, i = [], 200
    while i < len(df) - 2:
        if c.iloc[i] > sma200.iloc[i] and r2.iloc[i] < rsi_max:
            entry = df["Open"].iloc[i + 1] * (1 + SPREAD)
            stop = entry - k_atr * atr.iloc[i]
            risk = entry - stop
            exit_px, j = None, i + 1
            while j < len(df) and j <= i + max_days:
                bar = df.iloc[j]
                if bar["Low"] <= stop:
                    exit_px = min(stop, bar["Open"])
                    break
                if bar["Close"] > sma5.iloc[j]:
                    exit_px = bar["Close"]
                    break
                j += 1
            if exit_px is None:
                j = min(j, len(df) - 1)
                exit_px = df["Close"].iloc[j]
            exit_px *= 1 - SPREAD
            out.append({"symbol": sym, "date": df.index[i + 1], "R": (exit_px - entry) / risk,
                        "ret_pct": (exit_px / entry - 1) * 100, "days": j - i})
            i = j + 1
        else:
            i += 1
    return out


def run(universe, label):
    data = yf.download(universe, period="2y", interval="1d", group_by="ticker", auto_adjust=True,
                       progress=False, threads=True)
    for rsi_max, k_atr, max_days in [(10, 2.0, 5), (5, 2.0, 5), (10, 3.0, 7), (5, 3.0, 7)]:
        rows = []
        for sym in universe:
            try:
                df = data[sym].dropna()
            except KeyError:
                continue
            if len(df) > 260:
                rows += trades_for(sym, df, rsi_max, k_atr, max_days)
        t = pd.DataFrame(rows)
        if t.empty:
            continue
        print(f"{label:7} RSI2<{rsi_max:<2} Stop {k_atr} ATR, max {max_days} Tage: n={len(t):4}  "
              f"Treffer {(t['R'] > 0).mean():4.0%}  Schnitt {t['R'].mean():+.2f} R  "
              f"Median Haltedauer {t['days'].median():.0f} T  schlechtester {t['R'].min():+.1f} R")


if __name__ == "__main__":
    run(UNIVERSE, "Aktien")
    run(CRYPTO_UNIVERSE, "Krypto")
