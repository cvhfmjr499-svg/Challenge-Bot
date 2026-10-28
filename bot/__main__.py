"""Command line: python -m bot <command>"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

from . import engine, export, market, risk, scanner
from .assets import normalize
from .runner import update
from .config import floor_equity, goal_equity, load_config, target_equity
from .state import (NY, STATE_PATH, equity, load_state, log_event, new_state, now_utc,
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


def cmd_update(args, cfg):
    state = _load()
    update(state, cfg, now_utc())
    save_state(state)
    print_status(state, cfg)


def print_status(state, cfg):
    eq = equity(state)
    fl = floor_equity(cfg, state["peak_equity"])
    phase = {"ACTIVE": "Phase 1: Challenge", "FUNDED": "Phase 2: bestanden, Ziel 10.000 $",
             "FAILED": "Verlustgrenze gerissen", "GOAL": "10.000-$-Ziel erreicht"}
    tg = target_equity(cfg) if state["status"] == "ACTIVE" else goal_equity(cfg)
    print(f"Status:      {state['status']}  ({phase.get(state['status'], '')})")
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
            ts = datetime.fromisoformat(e["ts"]).astimezone(NY)
            print(f"  {ts:%Y-%m-%d %H:%M} NY  {e['text']}")


def cmd_propose(args, cfg):
    state = _load()
    now = now_utc()
    update(state, cfg, now)
    args.symbol = normalize(args.symbol)
    entry_type, entry = args.type, args.entry
    if entry_type == "market":
        entry = round(market.last_price(args.symbol), 2)
    prop = risk.Proposal(args.symbol.upper(), entry, args.stop, args.target, entry_type, args.reason)
    d = risk.evaluate(cfg, state, prop, now.isoformat())
    print(json.dumps({"proposal": prop.__dict__, "approved": d.approved, "qty": d.qty,
                      "risk_amount": d.risk_amount, "rejections": d.rejections,
                      "notes": d.notes}, indent=2, ensure_ascii=False))
    if d.approved and not args.dry_run:
        engine.place_order(state, prop, d, now, cfg)
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
    sym = normalize(args.symbol)
    if sym not in state["positions"]:
        sys.exit(f"Keine Position {sym}.")
    state["positions"][sym]["close_requested"] = True
    log_event(state, now_utc().isoformat(), f"{sym}: Schließen zur nächsten Kerze angefordert.")
    save_state(state)
    print(f"{sym} wird zum Eröffnungskurs der nächsten 5-Min-Kerze geschlossen.")


SCANS = {
    "stocks": ("Aktien", scanner.UNIVERSE, "SPY"),
    "crypto": ("Krypto", scanner.CRYPTO_UNIVERSE, "BTC-USD"),
}


def cmd_scan(args, cfg):
    markets = list(SCANS) if args.market == "all" else [args.market]
    results = {}
    for m in markets:
        label, universe, bench = SCANS[m]
        reg, rows = scanner.scan(cfg, universe, args.top, bench)
        results[m] = {"regime": reg, "benchmark": bench, "candidates": rows}
    if args.json:
        print(json.dumps(results, indent=2))
        return
    for m, res in results.items():
        print(f"\n== {SCANS[m][0]} ==  Regime ({res['benchmark']} vs. 50/200-Tage-Linie): {res['regime']}"
              f"   RS3M% relativ zu {res['benchmark']}")
        print_scan(res["candidates"])
        if not res["candidates"]:
            print("  (keine Kandidaten)")


def print_scan(rows):
    print(f"{'Symbol':9} {'Kurs':>10} {'Einstieg':>9} {'Stop':>9} {'Ziel':>9} {'Stop%':>6} "
          f"{'Abst%':>6} {'Kontr.':>6} {'RS3M%':>6} {'Score':>6}")
    for r in rows:
        print(f"{r['symbol']:9} {r['close']:10.4g} {r['entry']:9.4g} {r['stop']:9.4g} {r['target']:9.4g} "
              f"{r['stop_pct']:6.2f} {r['dist_pct']:6.2f} {r['contraction']:6.2f} {r['rs_3m_pct']:6.1f} "
              f"{r['score']:6.1f}")


def cmd_live(args, cfg):
    from . import live
    live.run(use_sync=not args.no_sync, port=args.port, open_browser=not args.no_browser)


def cmd_tick(args, cfg):
    """One step for frequent runners (GitHub Actions every 5 min): settle + export the phone page data."""
    from .runner import curve_due
    state = _load()
    now = now_utc()
    update(state, cfg, now, record_curve=curve_due(state, now))
    state["last_tick"] = now.isoformat()
    save_state(state)
    export.export_web(state, cfg, Path(args.out))
    print(f"{state['status']} Equity {equity(state):.2f} $  Positionen {len(state['positions'])}  Orders {len(state['orders'])}")


def cmd_export(args, cfg):
    state = _load()
    counts = export.export(state, cfg, Path(args.out), now_utc().isoformat())
    print(json.dumps(counts))


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
    p.add_argument("--market", choices=["all", "stocks", "crypto"], default="all")
    p.add_argument("--json", action="store_true"); p.set_defaults(f=cmd_scan)
    p = sub.add_parser("live", help="Live-Ansicht im Browser + minütliche Abrechnung")
    p.add_argument("--no-sync", action="store_true", help="ohne GitHub-Abgleich")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--no-browser", action="store_true")
    p.set_defaults(f=cmd_live)
    p = sub.add_parser("tick", help="Ein Abrechnungsschritt + Daten für die Handy-Seite")
    p.add_argument("--out", default="docs/data"); p.set_defaults(f=cmd_tick)
    p = sub.add_parser("export"); p.add_argument("--out", default="data/dashboard")
    p.set_defaults(f=cmd_export)
    args = ap.parse_args()
    if args.cmd == "propose" and args.type != "market" and args.entry <= 0:
        ap.error("--entry ist für stop/limit Orders nötig.")
    args.f(args, load_config())


if __name__ == "__main__":
    main()
