"""One step of the free test account (no challenge rules): settle, open new trades, and after the
deadline close everything. Runs every 5 minutes on GitHub Actions (.github/workflows/test-tick.yml).

Usage: python scripts/free_step.py --until "2026-11-08 11:00"   (Berlin time)
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
os.environ.setdefault("BOT_STATE", str(ROOT / "data" / "free" / "state.json"))
os.environ.setdefault("BOT_CONFIG", str(ROOT / "config_free.yaml"))
sys.path.insert(0, str(ROOT))

from bot import dips  # noqa: E402
from bot.config import load_config  # noqa: E402
from bot.intraday import CRYPTO, STOCKS  # noqa: E402
from bot.state import buying_power  # noqa: E402

# Entry rules from the 7.11. review (LEARNINGS.md): extreme pullbacks only (15 instead of 10 for more trades),
# no loosened trend entries.
SCAN = {"rsi_max": 15, "trend_rsi": 15, "short": True, "target_atr": 6.0, "min_stop_pct": 2.5}
SLOTS = 25
MAX_CRYPTO_SAME_SIDE = 2


def bot(*args):
    return subprocess.run([sys.executable, "-m", "bot", *args], cwd=ROOT, capture_output=True, text=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--until", required=True, help='Berlin time, e.g. "2026-11-08 11:00"')
    args = ap.parse_args()
    berlin = ZoneInfo("Europe/Berlin")
    end = datetime.strptime(args.until, "%Y-%m-%d %H:%M").replace(tzinfo=berlin)
    now = datetime.now(berlin)

    bot("update")
    state = json.loads(Path(os.environ["BOT_STATE"]).read_text())

    if now >= end:
        # Deadline: no new trades, cancel waiting orders, sell everything at the next candle.
        for o in state["orders"]:
            bot("cancel", str(o["id"]))
        for sym, p in state["positions"].items():
            if not p.get("close_requested"):
                bot("close", sym)
        print(f"Ende erreicht: {len(state['positions'])} Positionen werden geschlossen.")
        return

    busy = set(state["positions"]) | {o["symbol"] for o in state["orders"]}
    free = buying_power(state, load_config()) - sum(abs(o["qty"]) * o["entry"] for o in state["orders"])
    slots = SLOTS - len(busy)
    if slots <= 0 or free <= 50:
        print(f"Kein Platz: {len(busy)} offen, freie Kaufkraft {free:.0f} $")
        return
    ny = datetime.now(ZoneInfo("America/New_York"))
    stocks_open = ny.weekday() < 5 and (9, 35) <= (ny.hour, ny.minute) < (15, 30)
    symbols = CRYPTO + (STOCKS if stocks_open else [])
    # Crypto coins move together: at most MAX_CRYPTO_SAME_SIDE crypto trades in one direction
    # (8.11.: BTC, AVAX and SOL long all fell at once, -65 $).
    sides = [("short" if p["qty"] < 0 else "long") for s, p in state["positions"].items() if s.endswith("-USD")]
    sides += [("short" if o["qty"] < 0 else "long") for o in state["orders"] if o["symbol"].endswith("-USD")]
    picks = []
    for c in dips.scan(symbols=symbols, **SCAN):
        if c["symbol"] in busy:
            continue
        if c["symbol"].endswith("-USD"):
            if sides.count(c["side"]) >= MAX_CRYPTO_SAME_SIDE:
                continue
            sides.append(c["side"])
        picks.append(c)
    for c in picks[:slots]:
        side = "über" if c["side"] == "long" else "unter"
        r = bot("propose", c["symbol"], "--type", "market", "--side", c["side"], "--stop", str(c["stop"]),
                "--target", str(c["target"]), "--expires-min", "10",
                "--reason", f"{c['side'].capitalize()}: RSI2 {c['rsi2']}, {side} EMA50")
        print(c["symbol"], c["side"], "platziert" if "Order platziert" in r.stdout else "abgelehnt")


if __name__ == "__main__":
    main()
