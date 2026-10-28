"""Persistent account state (state.json). Only the bot writes this file."""
import json
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from .config import ROOT, start_balance

NY = ZoneInfo("America/New_York")
STATE_PATH = ROOT / "data" / "state.json"


def now_utc():
    return datetime.now(timezone.utc)


def new_state(cfg):
    start = start_balance(cfg)
    return {
        "status": "ACTIVE",  # ACTIVE | PASSED | FAILED
        "created_at": now_utc().isoformat(),
        "cash": start,
        "peak_equity": start,
        "positions": {},
        "orders": [],
        "closed_trades": [],
        "cursor": {},
        "equity_curve": [],
        "events": [],
        "next_id": 1,
    }


def load_state(path=STATE_PATH):
    with open(path) as f:
        return json.load(f)


def save_state(state, path=STATE_PATH):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.replace(path)


def log_event(state, ts, text):
    state["events"].append({"ts": ts, "text": text})


def equity(state, prices=None):
    """Cash plus positions marked at `prices` (default: each position's last price)."""
    prices = prices or {}
    return state["cash"] + sum(
        p["qty"] * prices.get(sym, p["last_price"]) for sym, p in state["positions"].items()
    )


def ny_date(ts_iso):
    return datetime.fromisoformat(ts_iso).astimezone(NY).date()
