"""Risk guard: hard-coded challenge rules. Claude proposes, this code decides."""
import math
from dataclasses import dataclass, field

from .config import floor_equity, start_balance, target_equity
from .state import equity, ny_date


@dataclass
class Proposal:
    symbol: str
    entry: float
    stop: float
    target: float
    entry_type: str = "stop"  # stop (breakout) | limit
    reason: str = ""


@dataclass
class Decision:
    approved: bool
    qty: float = 0.0
    risk_amount: float = 0.0
    rejections: list = field(default_factory=list)
    notes: list = field(default_factory=list)


def committed_risk(state, cfg):
    """Worst-case loss of all open positions and pending orders if every stop is hit."""
    slip = cfg["execution"]["entry_slippage_cap_pct"] / 100
    total = 0.0
    for p in state["positions"].values():
        total += max(0.0, p["qty"] * (p["last_price"] - p["stop"]))
    for o in state["orders"]:
        total += o["qty"] * (o["entry"] * (1 + slip) - o["stop"])
    return total


def room(state, cfg):
    """Distance from current equity to the failure line, minus risk already committed."""
    eq = equity(state)
    return eq - floor_equity(cfg, state["peak_equity"]) - committed_risk(state, cfg)


def losing_streak(state):
    n = 0
    for t in reversed(state["closed_trades"]):
        if t["pnl"] >= 0:
            break
        n += 1
    return n


def realized_pnl_on(state, day):
    return sum(t["pnl"] for t in state["closed_trades"] if ny_date(t["exit_ts"]) == day)


def evaluate(cfg, state, prop: Proposal, now_iso):
    r = cfg["risk"]
    slip = cfg["execution"]["entry_slippage_cap_pct"] / 100
    rej, notes = [], []
    today = ny_date(now_iso)

    if state["status"] != "ACTIVE":
        rej.append(f"Challenge ist beendet ({state['status']}).")
    if prop.entry_type not in ("stop", "limit"):
        rej.append(f"Unbekannter Order-Typ {prop.entry_type}.")
    if not (prop.stop < prop.entry < prop.target):
        rej.append("Nur Long: Stop < Einstieg < Ziel erforderlich.")
        return Decision(False, rejections=rej)

    stop_pct = (prop.entry - prop.stop) / prop.entry * 100
    if stop_pct < r["min_stop_pct"]:
        rej.append(f"Stop zu eng ({stop_pct:.2f} % < {r['min_stop_pct']} %).")
    if stop_pct > r["max_stop_pct"]:
        rej.append(f"Stop zu weit ({stop_pct:.2f} % > {r['max_stop_pct']} %).")
    rr = round((prop.target - prop.entry) / (prop.entry - prop.stop), 2)
    if rr < r["min_reward_risk"]:
        rej.append(f"Chance/Risiko {rr:.2f} < {r['min_reward_risk']}.")

    busy = len(state["positions"]) + len(state["orders"])
    if busy >= r["max_open_positions"]:
        rej.append(f"Schon {busy} Positionen/Orders offen (max {r['max_open_positions']}).")
    if prop.symbol in state["positions"] or any(o["symbol"] == prop.symbol for o in state["orders"]):
        rej.append(f"{prop.symbol} ist schon offen oder bestellt.")

    streak = losing_streak(state)
    if (streak >= r["pause_after_losses"] and state["closed_trades"]
            and ny_date(state["closed_trades"][-1]["exit_ts"]) == today):
        rej.append(f"{streak} Verluste in Folge – Pause bis zum nächsten Handelstag.")
    day_pnl = realized_pnl_on(state, today)
    if day_pnl <= -start_balance(cfg) * r["daily_loss_limit_pct"] / 100:
        rej.append(f"Tagesverlust-Limit erreicht ({day_pnl:.2f} $).")

    eq = equity(state)
    free = room(state, cfg)
    budget = min(eq * r["risk_per_trade_pct"] / 100, free * r["max_room_fraction"])
    if budget <= 0:
        rej.append(f"Kein Risiko-Puffer mehr frei (Rest {free:.2f} $).")
        return Decision(False, rejections=rej)

    # Risk per share includes the worst allowed entry slippage.
    per_share = prop.entry * (1 + slip) - prop.stop
    qty = budget / per_share
    max_notional = min(eq * r["max_position_pct"] / 100, state["cash"])
    if qty * prop.entry * (1 + slip) > max_notional:
        qty = max_notional / (prop.entry * (1 + slip))
        notes.append("Größe durch Positions-/Cash-Limit begrenzt.")
    qty = math.floor(qty * 1000) / 1000 if r["allow_fractional"] else math.floor(qty)
    if qty <= 0:
        rej.append("Positionsgröße wäre 0.")

    risk_amount = qty * per_share
    if eq + qty * (prop.target - prop.entry) >= target_equity(cfg):
        notes.append("Dieser Trade allein könnte das Challenge-Ziel erreichen.")
    notes.append(f"Restpuffer vor Trade: {free:.2f} $, Budget: {budget:.2f} $.")
    return Decision(not rej, qty, round(risk_amount, 2), rej, notes)


def protect_stops(state, cfg, prices):
    """Raise stops so that all stops together cannot push equity below the floor.

    Needed for the trailing drawdown: when open profits lift the peak, the floor
    rises too, and the original stops would no longer fit in the remaining room.
    Returns a list of (symbol, old_stop, new_stop).
    """
    if not state["positions"]:
        return []
    eq = equity(state, prices)
    allowed = cfg["risk"]["protect_fraction"] * (eq - floor_equity(cfg, state["peak_equity"]))
    exposure = {s: max(0.0, p["qty"] * (prices.get(s, p["last_price"]) - p["stop"]))
                for s, p in state["positions"].items()}
    total = sum(exposure.values())
    if total <= allowed or total == 0:
        return []
    scale = max(0.0, allowed) / total
    changes = []
    for s, p in state["positions"].items():
        px = prices.get(s, p["last_price"])
        new_stop = round(px - (px - p["stop"]) * scale, 4)
        if new_stop > p["stop"]:
            changes.append((s, p["stop"], new_stop))
            p["stop"] = new_stop
    return changes
