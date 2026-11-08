#!/usr/bin/env bash
# Run the free test account every minute until END (Berlin), pushing its state for the phone page.
# Stops by itself after MAX_MIN minutes (default 110) so a caller can restart it in chunks.
# After END it keeps settling until every position is closed.
# Usage: scripts/free_loop.sh "2026-11-09 11:00" [MAX_MIN]
set -u
cd "$(dirname "$0")/.." || exit 1
UNTIL=$1; STOP_AT=$(( $(date +%s) + ${2:-110} * 60 ))
END=$(TZ=Europe/Berlin date -d "$UNTIL" +%s)
export BOT_STATE="$PWD/data/free/state.json" BOT_CONFIG="$PWD/config_free.yaml"
last_push=0
while :; do
  python3 scripts/free_step.py --until "$UNTIL" 2>&1 | grep -v Crumb
  open=$(python3 -c "import json,os;s=json.load(open(os.environ['BOT_STATE']));print(len(s['positions'])+len(s['orders']))")
  if [ "$(date +%s)" -ge $(( last_push + 120 )) ] || { [ "$(date +%s)" -ge "$END" ] && [ "$open" = 0 ]; }; then
    python3 -m bot web-export --out docs/test/data 2>&1 | grep -v Crumb
    git add data/free docs/test/data
    git diff --cached --quiet || git commit -qm "Test-Konto: Lauf (jede Minute)

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01DcrhSwCMQu5nBEAzzCUUZo"
    git pull -q --rebase origin main 2>/dev/null; git push -q origin main 2>/dev/null || echo "PUSH_REJECTED $(date +%H:%M)"
    last_push=$(date +%s)
  fi
  [ "$(date +%s)" -ge "$END" ] && [ "$open" = 0 ] && { echo "FERTIG: Endzeit erreicht, alles geschlossen"; exit 0; }
  [ "$(date +%s)" -ge "$STOP_AT" ] && { echo "ABSCHNITT: neu starten"; exit 0; }
  T=$(( $(date +%s) + 60 )); until [ "$(date +%s)" -ge "$T" ]; do sleep 5; done
done
