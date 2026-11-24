"""One step of the Kraken challenge account: settle, open crypto longs only, and after the deadline close
everything. Kraken Funded: no leverage, no shorts; config.yaml holds the risk rules (the guard enforces them).

Usage: python scripts/challenge_step.py --until "2026-12-01 22:00"   (Berlin time)
"""
import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent.parent
os.environ.setdefault("BOT_STATE", str(ROOT / "data" / "state.json"))
os.environ.setdefault("BOT_CONFIG", str(ROOT / "config.yaml"))
sys.path.insert(0, str(ROOT))

from bot import dips  # noqa: E402
from bot.intraday import CRYPTO  # noqa: E402
from bot.scanner import _px  # noqa: E402

# Crypto only, long only. 24.11.: the user wants as many trades as possible -> looser pullback rules
# (LEARNINGS.md: looser rules = more trades, but also more loss), smaller risk per trade in config.yaml.
SCAN = {"rsi_max": 30, "trend_rsi": 40, "short": False, "target_atr": 6.0, "min_stop_pct": 1.0}


def bot(*args):
    return subprocess.run([sys.executable, "-m", "bot", *args], cwd=ROOT, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", required=True, help='Berlin time, e.g. "2026-12-01 22:00"')
    args = ap.parse_args()
    berlin = ZoneInfo("Europe/Berlin")
    end = datetime.strptime(args.until, "%Y-%m-%d %H:%M").replace(tzinfo=berlin)

    bot("update")
    state = json.loads(Path(os.environ["BOT_STATE"]).read_text())
    if datetime.now(berlin) >= end:
        for o in state["orders"]:
            bot("cancel", str(o["id"]))
        for sym, p in state["positions"].items():
            if not p.get("close_requested"):
                bot("close", sym)
        print(f"Ende erreicht: {len(state['positions'])} Positionen werden geschlossen.")
        return
    if state.get("status") != "ACTIVE":
        print(f"Status {state.get('status')}: keine neuen Trades")
        return
    busy = set(state["positions"]) | {o["symbol"] for o in state["orders"]}
    for c in dips.scan(symbols=CRYPTO, **SCAN):
        if c["symbol"] in busy or c["side"] != "long":
            continue
        # The live price is often away from the last 5m close: keep the stop distance, but measure stop and
        # target from the price the market order would really get (the dry run tells it).
        dist = c["close"] - c["stop"]
        dry = bot("propose", c["symbol"], "--type", "market", "--stop", str(c["stop"]), "--target", str(c["target"]),
                  "--dry-run")
        try:
            entry = json.loads(dry.stdout[dry.stdout.index("{"):])["proposal"]["entry"]
        except ValueError:
            entry = c["close"]
        stop, target = _px(entry - dist), _px(entry + 3.4 * dist)
        r = bot("propose", c["symbol"], "--type", "market", "--side", "long", "--stop", str(stop),
                "--target", str(target), "--expires-min", "10", "--reason", f"Long: RSI2 {c['rsi2']}, über EMA50")
        if "Order platziert" in r.stdout:
            print(c["symbol"], "platziert")
        else:
            try:
                why = "; ".join(json.loads(r.stdout[r.stdout.index("{"):])["rejections"])
            except ValueError:
                why = (r.stdout + r.stderr).strip()[-160:]
            print(c["symbol"], "abgelehnt:", why)


if __name__ == "__main__":
    main()
