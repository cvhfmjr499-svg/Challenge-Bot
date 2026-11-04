"""Backtest short dip-buys in crypto on 5-minute bars (last ~7 days), with Kraken costs.

Entry : price above EMA(50) (short-term uptrend) and RSI(2) < threshold -> buy next bar's open.
Exit  : first close above EMA(5), or stop at k * ATR(14) below entry, or after max_bars.
Costs : 0.04 % spread per side. Results in R and in % of position.
"""
import sys

import numpy as np
import pandas as pd
import yfinance as yf

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from bot.intraday import CRYPTO  # noqa: E402

SPREAD = 0.0004


def rsi(c, n=2):
    d = c.diff()
    up = d.clip(lower=0).ewm(alpha=1 / n, adjust=False).mean()
    dn = (-d.clip(upper=0)).ewm(alpha=1 / n, adjust=False).mean()
    return 100 - 100 / (1 + up / dn.replace(0, np.nan))


def run(rsi_max, k_atr, max_bars, data, side="long"):
    rows = []
    for sym, df in data.items():
        c = df["Close"]
        ema50, ema5 = c.ewm(span=50).mean(), c.ewm(span=5).mean()
        tr = pd.concat([df["High"] - df["Low"], (df["High"] - c.shift()).abs(), (df["Low"] - c.shift()).abs()], axis=1).max(axis=1)
        atr = tr.rolling(14).mean()
        r2 = rsi(c)
        i = 60
        while i < len(df) - 2:
            s = 1 if side == "long" else -1
            sig = (c.iloc[i] > ema50.iloc[i] and r2.iloc[i] < rsi_max) if s > 0 else \
                  (c.iloc[i] < ema50.iloc[i] and r2.iloc[i] > 100 - rsi_max)
            if sig:
                entry = df["Open"].iloc[i + 1] * (1 + s * SPREAD)
                stop = entry - s * k_atr * atr.iloc[i]
                exit_px, j = None, i + 1
                while j < len(df) and j <= i + max_bars:
                    b = df.iloc[j]
                    if (b["Low"] <= stop) if s > 0 else (b["High"] >= stop):
                        exit_px = min(stop, b["Open"]) if s > 0 else max(stop, b["Open"])
                        break
                    if (b["Close"] > ema5.iloc[j]) if s > 0 else (b["Close"] < ema5.iloc[j]):
                        exit_px = b["Close"]
                        break
                    j += 1
                if exit_px is None:
                    j = min(j, len(df) - 1)
                    exit_px = c.iloc[j]
                exit_px *= 1 - s * SPREAD
                rows.append({"sym": sym, "R": s * (exit_px - entry) / abs(entry - stop), "pct": s * (exit_px / entry - 1) * 100})
                i = j + 1
            else:
                i += 1
    t = pd.DataFrame(rows)
    print(f"{side:5} RSI2<{rsi_max:<3} Stop {k_atr} ATR, max {max_bars*5:3} Min: n={len(t):4}  Treffer {(t['R'] > 0).mean():4.0%}  "
          f"Schnitt {t['R'].mean():+.2f} R / {t['pct'].mean():+.3f} %  Summe {t['pct'].sum():+.1f} %")


if __name__ == "__main__":
    data = {}
    for s in CRYPTO:
        df = yf.Ticker(s).history(period="7d", interval="5m").dropna()
        if len(df) > 200:
            data[s] = df
    for side in ("long", "short"):
        for args in [(10, 2.0, 12), (5, 3.0, 18)]:
            run(*args, data, side)
