"""Export account state + price candles as JSON files for the dashboard."""
import json
from pathlib import Path

import yfinance as yf

from . import risk
from .config import floor_equity, goal_equity, target_equity
from .state import equity

PHASES = {"ACTIVE": "Phase 1: Challenge", "FUNDED": "Phase 2: auf dem Weg zu 10.000 $",
          "FAILED": "Verlustgrenze gerissen", "GOAL": "10.000 $ erreicht"}


def _trade_rows(state):
    rows = []
    for i, t in enumerate(state["closed_trades"], 1):
        rows.append({"id": f"T{i}", "symbol": t["symbol"], "status": "geschlossen",
                     "opened": t["entry_ts"], "closed": t["exit_ts"], "qty": t["qty"],
                     "entry": t["entry_price"], "exit": t["exit_price"], "stop": None,
                     "target": None, "pnl": t["pnl"], "r": t["r"], "result": t["exit_reason"],
                     "reason": t.get("reason", "")})
    for sym, p in state["positions"].items():
        rows.append({"id": f"P-{sym}", "symbol": sym, "status": "offen", "opened": p["entry_ts"],
                     "closed": None, "qty": p["qty"], "entry": p["entry_price"],
                     "exit": p["last_price"], "stop": p["stop"], "target": p["target"],
                     "pnl": round(p["qty"] * (p["last_price"] - p["entry_price"]), 2),
                     "r": round((p["last_price"] - p["entry_price"]) * p["qty"] / p["initial_risk"], 2)
                     if p["initial_risk"] else None,
                     "result": "läuft", "reason": p.get("reason", "")})
    for o in state["orders"]:
        rows.append({"id": f"O{o['id']}", "symbol": o["symbol"], "status": "Order",
                     "opened": o["created_at"], "closed": o["expires_at"], "qty": o["qty"],
                     "entry": o["entry"], "exit": None, "stop": o["stop"], "target": o["target"],
                     "pnl": None, "r": None, "result": "wartet", "reason": o.get("reason", "")})
    return rows


def _candles(symbols):
    rows = []
    for sym in symbols:
        df = yf.Ticker(sym).history(period="5d", interval="5m", prepost=False)
        for ts, b in df.dropna().tail(300).iterrows():
            rows.append({"symbol": sym, "ts": ts.tz_convert("UTC").isoformat(),
                         "open": round(float(b["Open"]), 6), "high": round(float(b["High"]), 6),
                         "low": round(float(b["Low"]), 6), "close": round(float(b["Close"]), 6)})
    return rows


def export(state, cfg, out: Path, now_iso):
    out.mkdir(parents=True, exist_ok=True)
    eq = equity(state)
    trades = state["closed_trades"]
    goal = target_equity(cfg) if state["status"] == "ACTIVE" else goal_equity(cfg)
    summary = [{
        "status": state["status"], "phase": PHASES.get(state["status"], state["status"]),
        "equity": round(eq, 2), "cash": round(state["cash"], 2),
        "floor": round(floor_equity(cfg, state["peak_equity"]), 2), "goal": round(goal, 2),
        "start": float(cfg["challenge"]["start_balance"]),
        "to_goal": round(goal - eq, 2), "room": round(risk.room(state, cfg), 2),
        "trades": len(trades), "wins": sum(t["pnl"] > 0 for t in trades),
        "pnl": round(sum(t["pnl"] for t in trades), 2), "open": len(state["positions"]),
        "orders": len(state["orders"]), "updated": now_iso,
    }]
    curve = [{"ts": state["created_at"], "equity": float(cfg["challenge"]["start_balance"]),
              "floor": round(floor_equity(cfg, float(cfg["challenge"]["start_balance"])), 2)}]
    curve += [{"ts": p["ts"], "equity": p["equity"], "floor": p["floor"]} for p in state["equity_curve"]]
    trade_rows = _trade_rows(state)
    # Chart symbols: open/ordered first, then the latest closed trades, BTC always as a fallback.
    symbols = list(dict.fromkeys(
        [r["symbol"] for r in trade_rows if r["status"] != "geschlossen"]
        + [t["symbol"] for t in reversed(trades)][:4] + ["BTC-USD"]))
    files = {"summary": summary, "equity": curve, "trades": trade_rows, "candles": _candles(symbols)}
    for name, rows in files.items():
        (out / f"{name}.json").write_text(json.dumps(rows))
    return {k: len(v) for k, v in files.items()}


def chart_symbols(state):
    """Symbols worth a chart: open, ordered, recently traded, plus the big coins."""
    s = ([p for p in state["positions"]] + [o["symbol"] for o in state["orders"]]
         + [t["symbol"] for t in reversed(state["closed_trades"])] + ["BTC-USD", "SOL-USD", "ETH-USD"])
    return list(dict.fromkeys(s))[:8]


def live_payload(state, cfg):
    eq = equity(state)
    goal = target_equity(cfg) if state["status"] == "ACTIVE" else goal_equity(cfg)
    floor = floor_equity(cfg, state["peak_equity"])
    return {
        "status": state["status"], "phase": PHASES.get(state["status"], state["status"]),
        "equity": round(eq, 2), "cash": round(state["cash"], 2), "goal": round(goal, 2),
        "floor": round(floor, 2), "headroom": round(eq - floor, 2), "room": round(risk.room(state, cfg), 2),
        "positions": [{"symbol": s, **p} for s, p in state["positions"].items()],
        "orders": state["orders"],
        "trades": state["closed_trades"][-50:],
        "events": state["events"][-40:],
        "event_count": len(state["events"]),
        "symbols": chart_symbols(state),
        "last_tick": state.get("last_tick"),
    }


def candles_1m(symbols, keep=390):
    out = {}
    for sym in symbols:
        df = yf.Ticker(sym).history(period="2d", interval="1m", prepost=False).dropna().tail(keep)
        out[sym] = [{"time": int(ts.timestamp()), "open": round(float(b["Open"]), 6),
                     "high": round(float(b["High"]), 6), "low": round(float(b["Low"]), 6),
                     "close": round(float(b["Close"]), 6)} for ts, b in df.iterrows()]
    return out


def export_web(state, cfg, out: Path):
    """Files for the phone page (GitHub Pages): data/state.json and data/candles.json."""
    out.mkdir(parents=True, exist_ok=True)
    (out / "state.json").write_text(json.dumps(live_payload(state, cfg)))
    (out / "candles.json").write_text(json.dumps(candles_1m(chart_symbols(state))))
