#!/usr/bin/env bash
# Free test account (no challenge rules): trade crypto dips until END (Berlin time), then close all.
# Usage: scripts/free_run.sh "2026-11-04 12:45"
set -u
cd "$(dirname "$0")/.." || exit 1
export BOT_STATE="$PWD/data/free/state.json" BOT_CONFIG="$PWD/config_free.yaml"
END=$(TZ=Europe/Berlin date -d "$1" +%s)
while [ "$(date +%s)" -lt "$END" ]; do
  python3 -m bot update 2>&1 | grep -v Crumb > /dev/null
  python3 - <<'EOF' 2>&1 | grep -v Crumb
import json, os, subprocess
from bot import dips
s = json.load(open(os.environ["BOT_STATE"]))
busy = set(s["positions"]) | {o["symbol"] for o in s["orders"]}
free_cash = s["cash"] - sum(o["qty"] * o["entry"] for o in s["orders"])
slots = 4 - len(busy)
if slots > 0 and free_cash > 50:
    for c in [c for c in dips.scan() if c["symbol"] not in busy][:slots]:
        r = subprocess.run(["python3", "-m", "bot", "propose", c["symbol"], "--type", "market",
                            "--stop", str(c["stop"]), "--target", str(c["target"]), "--expires-min", "10",
                            "--reason", f"Rücksetzer: RSI2 {c['rsi2']}, über EMA50"],
                           capture_output=True, text=True)
        print(c["symbol"], "platziert" if "Order platziert" in r.stdout else "abgelehnt")
EOF
  T=$(( $(date +%s) + 120 )); until [ "$(date +%s)" -ge "$T" ] || [ "$(date +%s)" -ge "$END" ]; do sleep 5; done
done
# Deadline: cancel waiting orders, close all positions at the next candle, settle.
python3 - <<'EOF'
import json, os, subprocess
s = json.load(open(os.environ["BOT_STATE"]))
for o in s["orders"]:
    subprocess.run(["python3", "-m", "bot", "cancel", str(o["id"])])
for sym in s["positions"]:
    subprocess.run(["python3", "-m", "bot", "close", sym])
EOF
T=$(( $(date +%s) + 90 )); until [ "$(date +%s)" -ge "$T" ]; do sleep 5; done
python3 -m bot update 2>&1 | grep -v Crumb > /dev/null
python3 -m bot status --events 60
