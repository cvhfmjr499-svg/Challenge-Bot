from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent


def load_config(path=None):
    with open(path or ROOT / "config.yaml") as f:
        return yaml.safe_load(f)


def start_balance(cfg):
    return float(cfg["challenge"]["start_balance"])


def target_equity(cfg):
    return start_balance(cfg) * (1 + cfg["challenge"]["profit_target_pct"] / 100)


def drawdown_amount(cfg):
    return start_balance(cfg) * cfg["challenge"]["max_drawdown_pct"] / 100


def floor_equity(cfg, peak):
    """Equity level at which the challenge is failed."""
    ch = cfg["challenge"]
    start = start_balance(cfg)
    if not ch["trailing_drawdown"]:
        return start - drawdown_amount(cfg)
    floor = max(start, peak) - drawdown_amount(cfg)
    if ch.get("trailing_locks_at_start"):
        floor = min(floor, start)
    return floor
