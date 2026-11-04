#!/usr/bin/env bash
# Publish the free test account to the phone page (?konto=test) every 2 minutes until END (Berlin).
# Usage: scripts/publish_test.sh "2026-11-04 12:50"
set -u
cd "$(dirname "$0")/.." || exit 1
END=$(TZ=Europe/Berlin date -d "$1" +%s)
while :; do
  BOT_STATE="$PWD/data/free/state.json" BOT_CONFIG="$PWD/config_free.yaml" \
    python3 -m bot web-export --out docs/test/data 2>&1 | grep -v Crumb
  git add docs/test/data
  git diff --cached --quiet || git commit -qm "Test-Konto: Stand für die Handy-Seite

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01DcrhSwCMQu5nBEAzzCUUZo"
  git pull -q --rebase origin main 2>/dev/null
  git push -q origin main 2>/dev/null || echo "PUSH_REJECTED $(date +%H:%M)"
  [ "$(date +%s)" -ge "$END" ] && exit 0
  T=$(( $(date +%s) + 120 )); until [ "$(date +%s)" -ge "$T" ]; do sleep 5; done
done
