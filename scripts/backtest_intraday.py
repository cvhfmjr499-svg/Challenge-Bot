"""Replay the intraday scanner over the last days of 5-minute bars and measure outcomes in R.

For every bar, the scanner is run on the data up to that bar. A signal becomes a buy-stop that
lives 12 bars (1 hour). Once filled, it exits at the stop, or at the target when a bar touches
it and closes below; a close above the target moves the stop to the target and the target one
R higher (the bot's rule). Stocks are closed at the session end, crypto after 24 hours.
At most one signal per symbol per hour is counted.
"""
import sys
from datetime import timedelta

import pandas as pd
import yfinance as yf

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
from bot import intraday  # noqa: E402
from bot.config import load_config  # noqa: E402

cfg = load_config()
cfg["aggressive"]["enabled"] = False
rows = []
for sym in intraday.STOCKS + intraday.CRYPTO:
    df = yf.Ticker(sym).history(period="7d", interval="5m", prepost=False).dropna()
    if len(df) < 120:
        continue
    crypto = sym.endswith("-USD")
    last_signal = None
    for i in range(60, len(df) - 2):
        ts = df.index[i]
        if last_signal is not None and ts - last_signal < timedelta(hours=1):
            continue
        if not crypto and (ts.hour, ts.minute) > (15, 30):
            continue
        setup = intraday._setup(sym, df.iloc[: i + 1], cfg, ts + timedelta(minutes=5))
        if not setup:
            continue
        last_signal = ts
        entry, stop, target = setup["entry"], setup["stop"], setup["target"]
        r = entry - stop
        fut = df.iloc[i + 1:]
        if not crypto:
            fut = fut[fut.index.date == ts.date()]
        else:
            fut = fut[fut.index < ts + timedelta(hours=24)]
        filled = None
        for k, (t, b) in enumerate(fut.iterrows()):
            if k >= 12:
                break
            if b["High"] >= entry:
                filled = k
                break
        if filled is None:
            outcome = None
        else:
            px = max(entry, fut.iloc[filled]["Open"])
            cur_stop, cur_target, outcome = stop, target, None
            for _, b in fut.iloc[filled:].iterrows():
                if b["Low"] <= cur_stop:
                    outcome = (min(cur_stop, b["Open"]) - px) / r
                    break
                if b["High"] >= cur_target:
                    if b["Close"] > cur_target:
                        cur_stop, cur_target = cur_target, cur_target + r
                        continue
                    outcome = (b["Close"] - px) / r
                    break
            if outcome is None:
                outcome = (fut.iloc[-1]["Close"] - px) / r      # closed at session end / 24 h
        rows.append({**setup, "ts": ts, "crypto": crypto, "hour_ny": ts.tz_convert("America/New_York").hour,
                     "filled": filled is not None, "R": outcome})

d = pd.DataFrame(rows)
d.to_csv("backtest_intraday.csv", index=False)
f = d[d["filled"]].copy()
print(f"Signale: {len(d)}, ausgeführt: {len(f)}")


def show(name, sub):
    if len(sub) == 0:
        print(f"{name:42} n=0")
        return
    print(f"{name:42} n={len(sub):3}  Trefferquote {(sub['R'] > 0).mean():5.0%}  "
          f"Schnitt {sub['R'].mean():+.2f} R  Summe {sub['R'].sum():+6.1f} R")


show("Alle (aktuelle Regeln)", f)
show("Volumen RV >= 0.7", f[f["rel_vol"] >= 0.7])
show("Volumen RV < 0.7", f[f["rel_vol"] < 0.7])
show("Schwung 1h >= +0.3 %", f[f["mom_1h_pct"] >= 0.3])
show("Schwung 1h < +0.3 %", f[f["mom_1h_pct"] < 0.3])
show("RV >= 0.7 UND Schwung >= 0.3 %", f[(f["rel_vol"] >= 0.7) & (f["mom_1h_pct"] >= 0.3)])
show("Score >= 0.5", f[f["score"] >= 0.5])
show("Score < 0.5", f[f["score"] < 0.5])
s = f[~f["crypto"]]
show("Aktien Mittag 11-13 Uhr NY", s[s["hour_ny"].between(11, 12)])
show("Aktien sonst", s[~s["hour_ny"].between(11, 12)])
show("Krypto", f[f["crypto"]])
show("Aktien", s)
