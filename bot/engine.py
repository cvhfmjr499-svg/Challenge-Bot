"""Local paper broker: fills orders against real 1- or 5-minute bars, conservatively.

Rules:
- Orders only see bars that start at or after the order was placed.
- Buy-stop (breakout): triggers when high >= entry; fills at max(entry, open) but
  never above entry * (1 + cap) (stop-limit). If the bar opens above the cap the
  order rests as a limit at the cap.
- Buy-limit: fills when low <= entry at min(entry, open).
- Market: fills at the next bar open if that is within entry * (1 + cap),
  otherwise rests as a limit at the cap.
- If stop and target are both touched in one bar, the stop wins.
- Kraken's spread (0.04 % per side) is charged on every fill and exit.
- The account fails if equity at the bar lows touches the floor (both phases).
- Phase 1 (ACTIVE) passes when equity at the bar close reaches +12 %: everything is
  closed and trading continues in phase 2 (FUNDED) until the goal equity (GOAL).
"""
from datetime import datetime, timedelta

from . import risk
from .assets import is_crypto
from .config import TRADING, floor_equity, goal_equity, target_equity
from .state import NY, equity, log_event

BAR = timedelta(minutes=5)


def order_expiry(created: datetime, symbol="", cfg=None):
    """Stocks: DAY order, expires 16:00 New York. Crypto (24/7): after N hours."""
    if is_crypto(symbol):
        return created + timedelta(hours=(cfg or {}).get("execution", {}).get("crypto_order_hours", 24))
    t = created.astimezone(NY)
    close = t.replace(hour=16, minute=0, second=0, microsecond=0)
    if t >= close:
        close += timedelta(days=1)
    while close.weekday() >= 5:
        close += timedelta(days=1)
    return close


def place_order(state, prop, decision, now: datetime, cfg=None, expires_minutes=None):
    oid = state["next_id"]
    state["next_id"] += 1
    order = {
        "id": oid,
        "symbol": prop.symbol,
        "type": prop.entry_type,
        "entry": prop.entry,
        "stop": prop.stop,
        "target": prop.target,
        "qty": decision.qty,
        "planned_risk": decision.risk_amount,
        "reason": prop.reason,
        "created_at": now.isoformat(),
        "expires_at": min(order_expiry(now, prop.symbol, cfg),
                          now + timedelta(minutes=expires_minutes) if expires_minutes
                          else order_expiry(now, prop.symbol, cfg)).isoformat(),
        "triggered": False,
    }
    state["orders"].append(order)
    log_event(state, now.isoformat(), f"Order #{oid} {prop.symbol} {prop.entry_type} "
              f"{decision.qty} @ {prop.entry} Stop {prop.stop} Ziel {prop.target}")
    return order


def stop_for_profit(cfg, position, profit):
    """Stop price at which closing (after stop slippage and spread) still earns `profit`."""
    ex = cfg["execution"]
    net = (1 - ex["stop_exit_slippage_pct"] / 100) * (1 - ex.get("spread_pct", 0) / 100)
    return (position["entry_price"] + profit / position["qty"]) / net


def move_stop(state, sym, new_stop, ts):
    """Raise a position's stop. Lowering it or setting it at or above the price is refused."""
    p = state["positions"].get(sym)
    if p is None:
        raise ValueError(f"Keine Position {sym}.")
    if new_stop <= p["stop"]:
        raise ValueError(f"Stop darf nur steigen (jetzt {p['stop']}, neu {new_stop:.4f}).")
    if new_stop >= p["last_price"]:
        raise ValueError(f"Stop {new_stop:.4f} liegt nicht unter dem Kurs {p['last_price']:.4f}.")
    log_event(state, ts, f"Stop {sym} nachgezogen {p['stop']} -> {round(new_stop, 4)}")
    p["stop"] = round(new_stop, 4)


def _close_position(state, sym, price, ts, why, cfg):
    price *= 1 - cfg["execution"].get("spread_pct", 0) / 100
    p = state["positions"].pop(sym)
    pnl = p["qty"] * (price - p["entry_price"])
    state["cash"] += p["qty"] * price
    r_value = p["initial_risk"] and pnl / p["initial_risk"]
    state["closed_trades"].append({
        "symbol": sym, "qty": p["qty"], "entry_price": p["entry_price"],
        "exit_price": round(price, 4), "entry_ts": p["entry_ts"], "exit_ts": ts,
        "pnl": round(pnl, 2), "r": round(r_value, 2), "exit_reason": why,
        "reason": p.get("reason", ""),
    })
    log_event(state, ts, f"EXIT {sym} {why} @ {price:.2f}  PnL {pnl:+.2f} $ ({r_value:+.2f} R)")


def _fill_order(state, o, bar, ts, cfg):
    cap = o["entry"] * (1 + cfg["execution"]["entry_slippage_cap_pct"] / 100)
    price = None
    if o["type"] == "limit":
        if bar["Low"] <= o["entry"]:
            price = min(o["entry"], bar["Open"])
    elif o["type"] == "market":
        if bar["Low"] <= cap:
            price = min(cap, bar["Open"])
    else:
        if not o["triggered"] and bar["High"] >= o["entry"]:
            o["triggered"] = True
            if bar["Open"] <= cap:
                price = max(o["entry"], bar["Open"])
            elif bar["Low"] <= cap:
                price = cap
        elif o["triggered"] and bar["Low"] <= cap:
            price = min(cap, bar["Open"])
    if price is None:
        return False
    price *= 1 + cfg["execution"].get("spread_pct", 0) / 100
    cost = o["qty"] * price
    if cost > state["cash"] + 1e-9:
        log_event(state, ts, f"Order #{o['id']} {o['symbol']} storniert: nicht genug Cash.")
        return True
    state["cash"] -= cost
    state["positions"][o["symbol"]] = {
        "qty": o["qty"], "entry_price": round(price, 4), "stop": o["stop"],
        "target": o["target"], "entry_ts": ts, "last_price": bar["Close"],
        "initial_risk": round(o["qty"] * (price - o["stop"]), 2), "reason": o["reason"],
        "close_requested": False,
    }
    log_event(state, ts, f"FILL {o['symbol']} {o['qty']} @ {price:.2f}")
    return True


def _manage_position(state, sym, bar, ts, cfg):
    p = state["positions"][sym]
    if p.get("close_requested"):
        _close_position(state, sym, bar["Open"], ts, "manuell", cfg)
        return
    stop_slip = cfg["execution"]["stop_exit_slippage_pct"] / 100
    if bar["Low"] <= p["stop"]:
        _close_position(state, sym, min(p["stop"], bar["Open"]) * (1 - stop_slip), ts, "Stop", cfg)
    elif bar["High"] >= p["target"] and p["entry_ts"] != ts:
        _close_position(state, sym, max(p["target"], bar["Open"]), ts, "Ziel", cfg)
    else:
        p["last_price"] = bar["Close"]


def _finish(state, prices, ts, status, why, cfg):
    for sym in list(state["positions"]):
        _close_position(state, sym, prices[sym], ts, why, cfg)
    state["orders"] = []
    state["status"] = status
    log_event(state, ts, f"STATUS {status} ({why}): Equity {equity(state):.2f} $")


def process_bars(state, cfg, bars, now: datetime):
    """Advance the simulation through `bars` ({symbol: DataFrame with OHLC, tz-aware index})."""
    complete = {s: df[df.index + df.attrs.get("bar", BAR) <= now] for s, df in bars.items()}
    timeline = sorted({ts for df in complete.values() for ts in df.index})

    for ts in timeline:
        if state["status"] not in TRADING:
            break
        ts_iso = ts.isoformat()
        lows = {}
        for sym, df in complete.items():
            if ts not in df.index:
                continue
            cur = state["cursor"].get(sym)
            if cur and ts <= datetime.fromisoformat(cur):
                continue
            bar = df.loc[ts]
            state["cursor"][sym] = ts_iso
            for o in [o for o in state["orders"] if o["symbol"] == sym]:
                if not (datetime.fromisoformat(o["created_at"]) <= ts
                        < datetime.fromisoformat(o["expires_at"])):
                    continue
                if _fill_order(state, o, bar, ts_iso, cfg):
                    state["orders"].remove(o)
                    # The fill bar may also hit the stop (conservative); targets wait a bar.
            if sym in state["positions"]:
                _manage_position(state, sym, bar, ts_iso, cfg)
            if sym in state["positions"]:
                lows[sym] = bar["Low"]

        closes = {s: p["last_price"] for s, p in state["positions"].items()}
        eq_close = equity(state)
        state["peak_equity"] = max(state["peak_equity"], eq_close)
        floor = floor_equity(cfg, state["peak_equity"])
        if equity(state, lows) <= floor:
            _finish(state, {s: lows.get(s, c) for s, c in closes.items()}, ts_iso,
                    "FAILED", "Verlustgrenze", cfg)
            break
        if state["status"] == "ACTIVE" and eq_close >= target_equity(cfg):
            _finish(state, closes, ts_iso, "FUNDED", "Challenge bestanden, weiter in Phase 2", cfg)
            state["passed_at"] = ts_iso
            continue
        if state["status"] == "FUNDED" and eq_close >= goal_equity(cfg):
            _finish(state, closes, ts_iso, "GOAL", "10.000-$-Ziel erreicht", cfg)
            break
        for sym, old, new in risk.protect_stops(state, cfg, closes):
            log_event(state, ts_iso, f"Stop {sym} angehoben {old:.2f} -> {new:.2f} (Puffer-Schutz)")

    for o in list(state["orders"]):
        if now >= datetime.fromisoformat(o["expires_at"]):
            state["orders"].remove(o)
            log_event(state, now.isoformat(), f"Order #{o['id']} {o['symbol']} abgelaufen.")
