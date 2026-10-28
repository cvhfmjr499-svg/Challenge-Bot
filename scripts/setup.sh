#!/usr/bin/env bash
# Prepare a fresh container: Python packages + tradermonty trading skills.
set -euo pipefail
python3 -m pip install -q -r "$(dirname "$0")/../requirements.txt" 2>&1 | grep -v "WARNING: Running pip" || true
if [ ! -f "$HOME/.claude/skills/market-breadth-analyzer/SKILL.md" ]; then
  tmp=$(mktemp -d)
  git clone -q --depth 1 https://github.com/tradermonty/claude-trading-skills.git "$tmp/cts"
  mkdir -p "$HOME/.claude/skills"
  cp -r "$tmp/cts/skills/"* "$HOME/.claude/skills/"
  rm -rf "$tmp"
fi
echo "Setup ok: $(ls "$HOME/.claude/skills" | wc -l) Skills"
