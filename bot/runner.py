"""One update step: fetch bars since the last processed one and advance the account."""
from datetime import datetime, timedelta

from . import engine, market
from .config import TRADING, floor_equity
from .state import equity


CURVE_EVERY = timedelta(minutes=15)


def curve_due(state, now):
    """Frequent runners (every 1-5 min) add an equity point only every 15 minutes."""
    last = state["equity_curve"][-1]["ts"] if state["equity_curve"] else state["created_at"]
    return now - datetime.fromisoformat(last) >= CURVE_EVERY


def update(state, cfg, now, record_curve=True):
    syms = set(state["positions"]) | {o["symbol"] for o in state["orders"]}
    if syms and state["status"] in TRADING:
        since = min([datetime.fromisoformat(state["cursor"].get(s, state["created_at"])) for s in syms]
                    + [datetime.fromisoformat(o["created_at"]) for o in state["orders"]])
        engine.process_bars(state, cfg, market.intraday_bars(sorted(syms), since), now)
    else:
        engine.process_bars(state, cfg, {}, now)
    if record_curve:
        state["equity_curve"].append({"ts": now.isoformat(), "equity": round(equity(state), 2),
                                      "floor": round(floor_equity(cfg, state["peak_equity"]), 2)})
