from datetime import datetime, timedelta

import pandas as pd
import pytest

from bot import engine, risk
from bot.config import floor_equity, load_config
from bot.state import NY, equity, new_state

T0 = datetime(2026, 10, 27, 9, 30, tzinfo=NY)  # Tuesday


@pytest.fixture
def cfg():
    return load_config()


@pytest.fixture
def state(cfg):
    s = new_state(cfg)
    s["created_at"] = (T0 - timedelta(hours=1)).isoformat()
    return s


def bars(rows, start=T0):
    """rows: list of (open, high, low, close), one per 5-minute bar."""
    idx = [start + timedelta(minutes=5 * i) for i in range(len(rows))]
    return pd.DataFrame(rows, columns=["Open", "High", "Low", "Close"], index=pd.DatetimeIndex(idx))


def place(cfg, state, sym="AAA", entry=100.0, stop=98.0, target=106.0, typ="stop", at=T0 - timedelta(minutes=10)):
    prop = risk.Proposal(sym, entry, stop, target, typ)
    d = risk.evaluate(cfg, state, prop, at.isoformat())
    assert d.approved, d.rejections
    engine.place_order(state, prop, d, at)
    return d


def run(cfg, state, data):
    end = max(df.index[-1] for df in data.values()) + timedelta(minutes=5)
    engine.process_bars(state, cfg, data, end)


def test_floor_trailing_and_fixed(cfg):
    assert floor_equity(cfg, 1000) == 970
    assert floor_equity(cfg, 1050) == 1020
    cfg["challenge"]["trailing_drawdown"] = False
    assert floor_equity(cfg, 1050) == 970
    cfg["challenge"]["trailing_drawdown"] = True
    cfg["challenge"]["trailing_locks_at_start"] = True
    assert floor_equity(cfg, 1050) == 1000


def test_position_size_respects_risk(cfg, state):
    d = place(cfg, state)
    # 0.75 % of 1000 = 7.50 $ budget, but max 50 % of the 30 $ room = 15 -> 7.50 wins
    assert d.risk_amount <= 7.5
    assert d.qty * 100 <= 600  # max 60 % of the account


def test_rejects_bad_reward_risk(cfg, state):
    d = risk.evaluate(cfg, state, risk.Proposal("AAA", 100, 98, 104), T0.isoformat())
    assert not d.approved and any("Chance/Risiko" in r for r in d.rejections)


def test_rejects_too_many_positions(cfg, state):
    place(cfg, state, "AAA")
    place(cfg, state, "BBB")
    d = risk.evaluate(cfg, state, risk.Proposal("CCC", 100, 98, 106), T0.isoformat())
    assert not d.approved


def test_combined_risk_never_exceeds_room(cfg, state):
    place(cfg, state, "AAA")
    place(cfg, state, "BBB")
    assert risk.committed_risk(state, cfg) < 30


def test_breakout_fill_then_target(cfg, state):
    d = place(cfg, state)
    run(cfg, state, {"AAA": bars([
        (99.5, 99.9, 99.4, 99.8),      # not triggered
        (99.9, 100.5, 99.8, 100.4),    # triggered, fills at 100
        (100.4, 103, 100.3, 102.9),
        (103, 106.5, 102.8, 106.2),    # target
    ])})
    t = state["closed_trades"][0]
    assert t["exit_reason"] == "Ziel" and t["entry_price"] == 100
    assert t["pnl"] == pytest.approx(d.qty * 6, abs=0.01)


def test_gap_above_cap_does_not_fill(cfg, state):
    place(cfg, state)
    run(cfg, state, {"AAA": bars([(101.5, 102, 101.2, 101.8)])})
    assert not state["positions"]


def test_stop_wins_when_both_touched(cfg, state):
    place(cfg, state)
    run(cfg, state, {"AAA": bars([(99.9, 100.2, 99.9, 100.1), (100, 107, 97, 100)])})
    assert state["closed_trades"][0]["exit_reason"] == "Stop"


def test_gap_down_through_stop_fills_at_open(cfg, state):
    place(cfg, state)
    run(cfg, state, {"AAA": bars([(99.9, 100.2, 99.9, 100.1), (97, 97.5, 96.5, 97)])})
    assert state["closed_trades"][0]["exit_price"] < 97


def test_losing_streak_pauses_trading(cfg, state):
    for i, sym in enumerate(["AAA", "BBB"]):
        place(cfg, state, sym)
    run(cfg, state, {s: bars([(99.9, 100.2, 99.9, 100.1), (99, 99, 97, 97.5)]) for s in ["AAA", "BBB"]})
    assert len(state["closed_trades"]) == 2
    later = T0 + timedelta(hours=1)
    d = risk.evaluate(cfg, state, risk.Proposal("CCC", 100, 98, 106), later.isoformat())
    assert not d.approved and any("Pause" in r for r in d.rejections)
    tomorrow = T0 + timedelta(days=1)
    assert risk.evaluate(cfg, state, risk.Proposal("CCC", 100, 98, 106), tomorrow.isoformat()).approved


def test_trailing_floor_raises_stops(cfg, state):
    place(cfg, state, target=130.0)
    # Price runs far up: peak rises, floor follows, stop must be lifted.
    run(cfg, state, {"AAA": bars([(99.9, 100.2, 99.9, 100.1)] + [(100 + i, 101 + i, 100 + i, 101 + i) for i in range(10)])})
    p = state["positions"]["AAA"]
    assert p["stop"] > 98
    worst = equity(state, {"AAA": p["stop"]})
    assert worst > floor_equity(cfg, state["peak_equity"])


def test_challenge_passes_and_flattens(cfg, state):
    state["cash"] = 1110.0
    state["peak_equity"] = 1110.0
    place(cfg, state)
    run(cfg, state, {"AAA": bars([(99.9, 100.2, 99.9, 100.1), (100.1, 103, 100.1, 103), (103, 106, 103, 105.9)])})
    assert state["status"] == "PASSED" and not state["positions"]


def test_order_expires_end_of_day(cfg, state):
    place(cfg, state)
    engine.process_bars(state, cfg, {}, T0.replace(hour=16, minute=1))
    assert not state["orders"]


def test_rejects_when_challenge_over(cfg, state):
    state["status"] = "FAILED"
    assert not risk.evaluate(cfg, state, risk.Proposal("AAA", 100, 98, 106), T0.isoformat()).approved


def test_market_order_fills_at_next_open_within_cap(cfg, state):
    place(cfg, state, typ="market")
    run(cfg, state, {"AAA": bars([(100.2, 100.4, 100.1, 100.3)])})
    assert state["positions"]["AAA"]["entry_price"] == 100.2


def test_market_order_does_not_chase(cfg, state):
    place(cfg, state, typ="market")
    run(cfg, state, {"AAA": bars([(101, 101.5, 100.9, 101.2)])})
    assert not state["positions"] and state["orders"]
