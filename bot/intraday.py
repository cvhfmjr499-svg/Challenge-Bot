"""Intraday breakout scan on 5-minute bars: above VWAP, short EMA trend up, close to the
high of the last 30 minutes. Suggestions only; the risk guard sizes and approves."""
from datetime import datetime, timedelta, timezone

import yfinance as yf

from .scanner import _px
from .state import NY

STOCKS = ["TSLA", "NVDA", "AMD", "PLTR", "COIN", "HOOD", "MU", "META", "AVGO", "NFLX", "MSTR",
          "AMZN", "AAPL", "MSFT", "GOOGL", "ARM", "SHOP", "UBER", "CRWD", "ANET", "SMH", "QQQ"]
CRYPTO = ["BTC-USD", "ETH-USD", "SOL-USD", "XRP-USD", "DOGE-USD", "AVAX-USD", "LINK-USD", "SUI20947-USD"]
RANGE_BARS = 6        # 30 minutes
MIDDAY_NY = (11, 12)  # no stock entries 11:00-12:59 New York (backtest 21.-30.10.: -0.30 R per trade)
MAX_STOP_PCT = 2.0    # wider than this is not an intraday trade


def _setup(sym, df, cfg, now, range_bars=RANGE_BARS):
    df = df[df.index + timedelta(minutes=5) <= now]          # completed bars only
    if len(df) < 30:
        return None
    if sym.endswith("-USD"):
        day = df.tail(78)                                    # last 6.5 hours
    else:
        day = df[df.index.date == df.index[-1].date()]       # today's session
        if len(day) < 8:
            return None
    typical = (day["High"] + day["Low"] + day["Close"]) / 3
    vol = day["Volume"].where(day["Volume"] > 0, 1)
    vwap = (typical * vol).cumsum().iloc[-1] / vol.cumsum().iloc[-1]
    c = df["Close"]
    ema9, ema21 = c.ewm(span=9).mean().iloc[-1], c.ewm(span=21).mean().iloc[-1]
    close = c.iloc[-1]
    if not (close > vwap and ema9 > ema21):
        return None
    rng = df.tail(range_bars)
    entry = _px(rng["High"].max() * 1.0005)
    dist = (entry / close - 1) * 100
    if not (0 <= dist <= 0.6 * max(1, range_bars / RANGE_BARS) ** 0.5):
        return None
    r = cfg["risk"]
    stop = _px(rng["Low"].min() * 0.9995)
    if (entry - stop) / entry * 100 < r["min_stop_pct"]:
        stop = _px(entry * (1 - r["min_stop_pct"] / 100))
    stop_pct = (entry - stop) / entry * 100
    if stop_pct > MAX_STOP_PCT:
        return None
    target = _px(entry + (entry - stop) * r["min_reward_risk"])
    mom = (close / c.iloc[-13] - 1) * 100                    # last hour
    rv = rng["Volume"].mean() / max(df["Volume"].tail(78).mean(), 1)
    return {"symbol": sym, "close": _px(close), "entry": entry, "stop": stop, "target": target,
            "stop_pct": round(stop_pct, 2), "dist_pct": round(dist, 2), "mom_1h_pct": round(mom, 2),
            "rel_vol": round(rv, 2), "vwap": _px(vwap),
            "score": round(mom + min(rv, 3) - stop_pct - dist, 2)}


def scan(cfg, markets=("stocks", "crypto"), top=8, range_bars=RANGE_BARS):
    now = datetime.now(timezone.utc)
    midday = now.astimezone(NY).hour in MIDDAY_NY
    syms = (STOCKS if "stocks" in markets and not midday else []) + (CRYPTO if "crypto" in markets else [])
    rows = []
    for sym in syms:
        df = yf.Ticker(sym).history(period="5d", interval="5m", prepost=False).dropna()
        if df.empty:
            continue
        row = _setup(sym, df, cfg, now, range_bars)
        if row:
            rows.append(row)
    rows.sort(key=lambda x: x["score"], reverse=True)
    return rows[:top]
