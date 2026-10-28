"""Live view for the PC: a local web page with a ticking chart, plus a runner that settles
orders, stops and targets every minute.

    python -m bot live            # with GitHub sync (default)
    python -m bot live --no-sync  # local only
"""
import json
import threading
import time
import traceback
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import yfinance as yf

from . import risk, sync
from .config import floor_equity, goal_equity, load_config, target_equity
from .export import PHASES
from .runner import update
from .state import STATE_PATH, equity, load_state, save_state

STATIC = Path(__file__).parent / "static"
CURVE_EVERY = timedelta(minutes=15)
PUSH_EVERY = timedelta(minutes=60)

runner_status = {"last_run": None, "last_error": None, "sync": None, "last_push": None}
_candle_cache = {}


def _step(cfg, use_sync):
    now = datetime.now(timezone.utc)
    if use_sync:
        err = sync.pull()
        runner_status["sync"] = err or "ok"
    state = load_state()
    events_before = len(state["events"])
    last_curve = state["equity_curve"][-1]["ts"] if state["equity_curve"] else state["created_at"]
    record = now - datetime.fromisoformat(last_curve) >= CURVE_EVERY
    update(state, cfg, now, record_curve=record)
    save_state(state)
    new_events = len(state["events"]) - events_before
    last_push = runner_status["last_push"]
    due = last_push is None or now - last_push >= PUSH_EVERY
    if use_sync and (new_events or (record and due)):
        err = sync.push(f"Live-Update: {new_events} neue Ereignisse")
        runner_status["sync"] = err or "ok"
        if not err:
            runner_status["last_push"] = now
    runner_status["last_run"] = now.isoformat()


def _runner(cfg, use_sync, interval):
    while True:
        try:
            _step(cfg, use_sync)
            runner_status["last_error"] = None
        except Exception as exc:  # keep the live view alive; show the error on the page
            runner_status["last_error"] = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        time.sleep(interval)


def _state_payload(cfg):
    state = load_state()
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
        "runner": runner_status,
    }


def _candles(symbol):
    hit = _candle_cache.get(symbol)
    if hit and time.time() - hit[0] < 20:
        return hit[1]
    df = yf.Ticker(symbol).history(period="2d", interval="1m", prepost=False).dropna()
    rows = [{"time": int(ts.timestamp()), "open": float(b["Open"]), "high": float(b["High"]),
             "low": float(b["Low"]), "close": float(b["Close"])} for ts, b in df.iterrows()]
    _candle_cache[symbol] = (time.time(), rows)
    return rows


class Handler(BaseHTTPRequestHandler):
    cfg = None

    def _send(self, code, body, ctype):
        data = body if isinstance(body, bytes) else body.encode()
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        url = urlparse(self.path)
        try:
            if url.path == "/":
                self._send(200, (STATIC / "live.html").read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/api/state":
                self._send(200, json.dumps(_state_payload(self.cfg)), "application/json")
            elif url.path == "/api/candles":
                sym = parse_qs(url.query).get("symbol", ["BTC-USD"])[0]
                self._send(200, json.dumps(_candles(sym)), "application/json")
            else:
                self._send(404, "nicht gefunden", "text/plain; charset=utf-8")
        except Exception as exc:
            self._send(500, json.dumps({"error": str(exc)}), "application/json")

    def log_message(self, *args):
        pass


def run(use_sync=True, port=8765, interval=60, open_browser=True):
    cfg = load_config()
    if not STATE_PATH.exists():
        raise SystemExit("Kein Konto gefunden (data/state.json).")
    if use_sync and not sync.available():
        print("Git nicht gefunden: Live-Ansicht läuft ohne GitHub-Abgleich.")
        use_sync = False
    threading.Thread(target=_runner, args=(cfg, use_sync, interval), daemon=True).start()
    Handler.cfg = cfg
    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    url = f"http://localhost:{port}"
    print(f"Live-Ansicht läuft: {url}   (Beenden mit Strg+C)")
    if open_browser:
        webbrowser.open(url)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Beendet.")
