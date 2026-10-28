"""Breakout candidate scan: uptrend + volatility contraction + close to a pivot.

Produces suggestions only. Claude reviews them and the risk guard sizes them.
"""
from . import market
from .assets import CRYPTO

UNIVERSE = [
    "AAPL", "MSFT", "NVDA", "AMZN", "GOOGL", "META", "AVGO", "TSLA", "AMD", "NFLX",
    "ORCL", "CRM", "ADBE", "NOW", "INTU", "QCOM", "MU", "AMAT", "LRCX", "KLAC",
    "ANET", "PANW", "CRWD", "FTNT", "PLTR", "SHOP", "UBER", "ABNB", "DDOG", "SNOW",
    "JPM", "GS", "MS", "V", "MA", "AXP", "BLK", "SCHW", "COIN", "HOOD",
    "LLY", "UNH", "ISRG", "VRTX", "REGN", "ABBV", "MRK", "TMO", "DHR", "BSX",
    "COST", "WMT", "HD", "LOW", "MCD", "SBUX", "NKE", "TJX", "CMG", "BKNG",
    "CAT", "DE", "GE", "HON", "ETN", "PH", "URI", "LMT", "RTX", "BA",
    "XOM", "CVX", "COP", "SLB", "FCX", "NEM", "LIN", "VST", "CEG", "NEE",
    "SPY", "QQQ", "IWM", "SMH", "XLK", "XLF", "XLE", "XLI", "XLV", "GLD",
]
CRYPTO_UNIVERSE = [f"{c}-USD" for c in CRYPTO]


def regime(daily, benchmark="SPY"):
    spy = daily.get(benchmark)
    if spy is None or len(spy) < 200:
        return "unbekannt"
    c = spy["Close"]
    above50, above200 = c.iloc[-1] > c.rolling(50).mean().iloc[-1], c.iloc[-1] > c.rolling(200).mean().iloc[-1]
    return "risk-on" if above50 and above200 else ("gemischt" if above200 else "risk-off")


def _px(x):
    """Round a price to a sensible tick: 0.01 above 100 $, finer for cheap coins."""
    return round(float(x), 2 if x >= 100 else 4 if x >= 1 else 6)


def _atr_pct(d, n):
    tr = (d["High"] - d["Low"]).combine((d["High"] - d["Close"].shift()).abs(), max)
    tr = tr.combine((d["Low"] - d["Close"].shift()).abs(), max)
    return (tr.rolling(n).mean() / d["Close"] * 100).iloc[-1]


def scan(cfg, universe=UNIVERSE, top=10, benchmark="SPY"):
    """Relative strength and regime are measured against `benchmark` (SPY or BTC-USD)."""
    daily = market.daily_bars(universe)
    r = cfg["risk"]
    spy_ret = None
    if benchmark in daily and len(daily[benchmark]) > 63:
        spy_ret = daily[benchmark]["Close"].iloc[-1] / daily[benchmark]["Close"].iloc[-64] - 1
    rows = []
    for sym, d in daily.items():
        if len(d) < 210:
            continue
        c = d["Close"]
        close = c.iloc[-1]
        sma50, sma200 = c.rolling(50).mean(), c.rolling(200).mean()
        if not (close > sma50.iloc[-1] > sma200.iloc[-1] and sma200.iloc[-1] > sma200.iloc[-21]):
            continue
        if (d["Close"] * d["Volume"]).tail(20).mean() < 50e6:
            continue
        pivot = d["High"].tail(10).max()
        entry = _px(pivot * 1.001)
        dist = (entry / close - 1) * 100
        if not (0 <= dist <= 3):
            continue
        stop = _px(d["Low"].tail(5).min() * 0.998)
        stop_pct = (entry - stop) / entry * 100
        if stop_pct < r["min_stop_pct"]:
            stop = _px(entry * (1 - r["min_stop_pct"] / 100))
            stop_pct = r["min_stop_pct"]
        if stop_pct > r["max_stop_pct"]:
            continue
        contraction = _atr_pct(d, 10) / _atr_pct(d, 50)
        rs = (close / c.iloc[-64] - 1) - (spy_ret or 0)
        target = _px(entry + (entry - stop) * r["min_reward_risk"])
        score = rs * 100 - contraction * 10 - dist - stop_pct
        rows.append({
            "symbol": sym, "close": _px(close), "entry": entry, "stop": stop,
            "target": target, "stop_pct": round(stop_pct, 2), "dist_pct": round(dist, 2),
            "contraction": round(contraction, 2), "rs_3m_pct": round(rs * 100, 1),
            "score": round(score, 1),
        })
    rows.sort(key=lambda x: x["score"], reverse=True)
    return regime(daily, benchmark), rows[:top]
