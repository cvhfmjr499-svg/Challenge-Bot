"""Command line: python -m bot <command>"""
import argparse
import json
import sys
from datetime import datetime

from . import engine, market, risk, scanner
from .config import floor_equity, load_config, target_equity
from .state import (STATE_PATH, equity, load_state, log_event, new_state, now_utc,
                    save_state)


def _load():
    if not STATE_PATH.exists():
        sys.exit("Kein Konto. Erst `python -m bot init` ausführen.")
    return load_state()


def cmd_init(args, cfg):
    if STATE_PATH.exists() and not args.force:
        sys.exit("Konto existiert schon. Mit --force neu starten (altes Konto geht verloren).")
    state = new_state(cfg)
    log_event(state, state["created_at"], f"Challenge gestartet mit {state['cash']:.2f} $")
    save_state(state)
    print_status(state, cfg)


def update(state, cfg, now):
    syms = set(state["positions"]) | {o["symbol"] for o in state["orders"]}
    if syms and state["status"] == "ACTIVE":
        since = min([datetime.fromisoformat(state["cursor"].get(s, state["created_at"])) for s in syms]
                    + [datetime.fromisoformat(o["created_at"]) for o in state["orders"]])
        engine.process_bars(state, cfg, market.intraday_bars(sorted(syms), since), now)
    else:
        engine.process_bars(state, cfg, {}, now)
    eq = equity(state)
    state["equity_curve"].append({"ts": now.isoformat(), "equity": round(eq, 2),
                                  "floor": round(floor_equity(cfg, state["peak_equity"]), 2)})


def cmd_update(args, cfg):
    state = _load()
    update(state, cfg, now_utc())
    save_state(state)
    print_status(state, cfg)


def print_status(state, cfg):
    eq = equity(state)
    fl = floor_equity(cfg, state["peak_equity"])
    tg = target_equity(cfg)
    print(f"Status:      {state['status']}")
    print(f"Equity:      {eq:9.2f} $   (Cash {state['cash']:.2f} $)")
    print(f"Ziel:        {tg:9.2f} $   noch {tg - eq:+.2f} $")
    print(f"Grenze:      {fl:9.2f} $   Abstand {eq - fl:.2f} $  (Höchststand {state['peak_equity']:.2f} $)")
    print(f"Freier Risiko-Puffer: {risk.room(state, cfg):.2f} $")
    for s, p in state["positions"].items():
        upnl = p["qty"] * (p["last_price"] - p["entry_price"])
        print(f"  POS {s:5} {p['qty']:>8} @ {p['entry_price']:.2f}  jetzt {p['last_price']:.2f}"
              f"  Stop {p['stop']:.2f}  Ziel {p['target']:.2f}  PnL {upnl:+.2f} $")
    for o in state["orders"]:
        print(f"  ORDER #{o['id']} {o['symbol']:5} {o['type']} {o['qty']} @ {o['entry']}"
              f"  Stop {o['stop']}  Ziel {o['target']}  bis {o['expires_at'][:16]}")
    trades = state["closed_trades"]
    if trades:
        wins = sum(t["pnl"] > 0 for t in trades)
        print(f"Trades: {len(trades)}  Gewinner {wins}  Summe {sum(t['pnl'] for t in trades):+.2f} $"
              f"  Summe R {sum(t['r'] for t in trades):+.2f}")


def cmd_status(args, cfg):
    state = _load()
    print_status(state, cfg)
    if args.events:
        for e in state["events"][-args.events:]:
            print(f"  {e['ts'][:16]}  {e['text']}")


def cmd_propose(args, cfg):
    state = _load()
    now = now_utc()
    update(state, cfg, now)
    entry_type, entry = args.type, args.entry
    if entry_type == "market":
        entry_type, entry = "limit", round(market.last_price(args.symbol), 2)
    prop = risk.Proposal(args.symbol.upper(), entry, args.stop, args.target, entry_type, args.reason)
    d = risk.evaluate(cfg, state, prop, now.isoformat())
    print(json.dumps({"proposal": prop.__dict__, "approved": d.approved, "qty": d.qty,
                      "risk_amount": d.risk_amount, "rejections": d.rejections,
                      "notes": d.notes}, indent=2, ensure_ascii=False))
    if d.approved and not args.dry_run:
        engine.place_order(state, prop, d, now)
        update(state, cfg, now)
        print("Order platziert.")
    save_state(state)


def cmd_cancel(args, cfg):
    state = _load()
    before = len(state["orders"])
    state["orders"] = [o for o in state["orders"] if o["id"] != args.order_id]
    if len(state["orders"]) == before:
        sys.exit(f"Keine Order #{args.order_id}.")
    log_event(state, now_utc().isoformat(), f"Order #{args.order_id} storniert.")
    save_state(state)
    print("Storniert.")


def cmd_close(args, cfg):
    state = _load()
    sym = args.symbol.upper()
    if sym not in state["positions"]:
        sys.exit(f"Keine Position {sym}.")
    state["positions"][sym]["close_requested"] = True
    log_event(state, now_utc().isoformat(), f"{sym}: Schließen zur nächsten Kerze angefordert.")
    save_state(state)
    print(f"{sym} wird zum Eröffnungskurs der nächsten 5-Min-Kerze geschlossen.")


def cmd_scan(args, cfg):
    reg, rows = scanner.scan(cfg, top=args.top)
    if args.json:
        print(json.dumps({"regime": reg, "candidates": rows}, indent=2))
        return
    print(f"Marktregime (SPY vs. 50/200-Tage-Linie): {reg}")
    print(f"{'Symbol':6} {'Kurs':>9} {'Einstieg':>9} {'Stop':>9} {'Ziel':>9} {'Stop%':>6} "
          f"{'Abst%':>6} {'Kontr.':>6} {'RS3M%':>6} {'Score':>6}")
    for r in rows:
        print(f"{r['symbol']:6} {r['close']:9.2f} {r['entry']:9.2f} {r['stop']:9.2f} {r['target']:9.2f} "
              f"{r['stop_pct']:6.2f} {r['dist_pct']:6.2f} {r['contraction']:6.2f} {r['rs_3m_pct']:6.1f} "
              f"{r['score']:6.1f}")


def main():
    ap = argparse.ArgumentParser(prog="bot", description="$1K-Challenge Paper-Bot")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init"); p.add_argument("--force", action="store_true"); p.set_defaults(f=cmd_init)
    sub.add_parser("update").set_defaults(f=cmd_update)
    p = sub.add_parser("status"); p.add_argument("--events", type=int, default=0); p.set_defaults(f=cmd_status)
    p = sub.add_parser("propose")
    p.add_argument("symbol")
    p.add_argument("--entry", type=float, default=0.0)
    p.add_argument("--stop", type=float, required=True)
    p.add_argument("--target", type=float, required=True)
    p.add_argument("--type", choices=["stop", "limit", "market"], default="stop")
    p.add_argument("--reason", default="")
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(f=cmd_propose)
    p = sub.add_parser("cancel"); p.add_argument("order_id", type=int); p.set_defaults(f=cmd_cancel)
    p = sub.add_parser("close"); p.add_argument("symbol"); p.set_defaults(f=cmd_close)
    p = sub.add_parser("scan"); p.add_argument("--top", type=int, default=10)
    p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_scan)
    args = ap.parse_args()
    if args.cmd == "propose" and args.type != "market" and args.entry <= 0:
        ap.error("--entry ist für stop/limit Orders nötig.")
    args.f(args, load_config())


if __name__ == "__main__":
    main()
