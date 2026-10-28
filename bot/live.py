"""Live view for the PC: serves the phone page (docs/index.html) locally, plus a runner that
settles orders, stops and targets every minute.

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
from urllib.parse import urlparse

from . import export, sync
from .config import ROOT, load_config
from .runner import curve_due, update
from .state import STATE_PATH, load_state, save_state

PAGE = ROOT / "docs" / "index.html"
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
    record = curve_due(state, now)
    update(state, cfg, now, record_curve=record)
    state["last_tick"] = now.isoformat()
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


def _candles(state):
    hit = _candle_cache.get("all")
    if hit and time.time() - hit[0] < 20:
        return hit[1]
    data = export.candles_1m(export.chart_symbols(state))
    _candle_cache["all"] = (time.time(), data)
    return data


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
            if url.path in ("/", "/index.html"):
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif url.path == "/data/state.json":
                self._send(200, json.dumps(export.live_payload(load_state(), self.cfg)), "application/json")
            elif url.path == "/data/candles.json":
                self._send(200, json.dumps(_candles(load_state())), "application/json")
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
