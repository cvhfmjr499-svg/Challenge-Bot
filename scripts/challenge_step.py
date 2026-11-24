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

# Crypto only, long only, extreme pullbacks only (LEARNINGS.md: looser rules = more trades, more loss).
SCAN = {"rsi_max": 10, "trend_rsi": 10, "short": False, "target_atr": 6.0, "min_stop_pct": 1.5}


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
        r = bot("propose", c["symbol"], "--type", "market", "--side", "long", "--stop", str(c["stop"]),
                "--target", str(c["target"]), "--expires-min", "10", "--reason", f"Long: RSI2 {c['rsi2']}, über EMA50")
        print(c["symbol"], "platziert" if "Order platziert" in r.stdout else "abgelehnt: " + r.stdout.strip()[-160:])
        if "Order platziert" in r.stdout:
            break  # max. 1 Krypto-Trade (config.yaml)


if __name__ == "__main__":
    main()
