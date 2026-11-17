"""Command-line entry point: python -m jin_agent <command>"""

from __future__ import annotations

import argparse
import json
import sys

from . import (VERSION, alerts, config, evaluator, llm, orchestrator,
               policy, scheduler, store)


def cmd_status(args):
    print(json.dumps(orchestrator.status(), ensure_ascii=False, indent=2))


def cmd_run(args):
    out = orchestrator.run(args.query, live=args.live, days=args.days,
                           limit=args.limit, save=not args.no_save)
    print(out["report"]["markdown"])
    print("\n--- METRICS ---")
    print(json.dumps(out["metrics"], ensure_ascii=False, indent=2))
    if out.get("saved"):
        print("\nSaved: " + str(out["saved"].get("md")))
    return 0 if out["ok"] else 1


def cmd_search(args):
    for item in store.search_archive(args.query, args.limit):
        print(f"[{item.get('score')}] {item.get('title')} | {item.get('source')} | {item.get('url')}")
    return 0


def cmd_sources(args):
    for s in policy.register():
        print(f"{s['tier']:>3}  {s['key']:<20} trust={s['trust']:<4} auto={s['auto']}  {s['url']}")
    return 0


def cmd_digest(args):
    out = orchestrator.digest()
    print("Digest saved:", (out.get("saved") or {}).get("md"))
    print("\n".join(out["report"]["markdown"].splitlines()[:20]))
    return 0


def cmd_eval(args):
    out = evaluator.run(live=args.live, save=True)
    print(json.dumps({"mode": out["mode"], "passed": out["passed"],
                      "metrics": out["metrics"], "safety": out["safety"],
                      "report": out.get("report_path")}, ensure_ascii=False, indent=2))
    return 0 if out["passed"] else 1


def cmd_schedule(args):
    cfg = config.load()
    store.init_db()
    worker = scheduler.Scheduler(cfg, offline=not args.live, poll_seconds=args.poll)
    worker.start()
    print("Scheduler chal raha hai. Rokne ke liye Ctrl+C.")
    try:
        while worker.is_alive():
            worker.join(1.0)
    except KeyboardInterrupt:
        pass
    finally:
        worker.stop()
        print("Scheduler band.")
    return 0


def cmd_serve(args):
    from . import server
    server.serve(args.port, args.open)
    return 0


def cmd_selftest(args):
    import unittest
    from pathlib import Path
    suite = unittest.TestLoader().discover(str(Path(__file__).resolve().parent / "tests"),
                                           pattern="test_*.py")
    result = unittest.TextTestRunner(verbosity=2).run(suite)
    return 0 if result.wasSuccessful() else 1


def cmd_classify(args):
    print(json.dumps(policy.classify(args.text), ensure_ascii=False, indent=2))
    return 0


def cmd_llm(args):
    print(json.dumps(llm.probe(config.load()), ensure_ascii=False, indent=2))
    return 0


def cmd_ci_gate(args):
    from . import ci_gate
    out = ci_gate.run(include_unittests=not args.skip_tests, queries=args.queries)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


def cmd_changes(args):
    from . import snapshots
    print(json.dumps({"ok": True, "changes": snapshots.recent_changes(args.limit),
                      "counts": snapshots.counts()},
                     ensure_ascii=False, indent=2))
    return 0


def cmd_channels(args):
    from . import channels as ch
    if args.add:
        row = ch.add_channel(args.add, origin="manual")
        print(json.dumps(row, ensure_ascii=False, indent=2))
    if args.remove:
        print(json.dumps(ch.remove_channel(args.remove), ensure_ascii=False, indent=2))
    if args.check:
        for c in (args.check.split(",") if args.check != "*" else
                  [r["channel"] for r in ch.list_channels()]):
            res = ch.check_channel(c, config.load())
            print(json.dumps(res, ensure_ascii=False)[:300])
    if args.discover:
        out = ch.run_discovery(config.load(), offline=args.offline)
        print(json.dumps(out, ensure_ascii=False, indent=2))
    rows = ch.list_channels(args.status or None)
    print(f"\nRegistry ({len(rows)} channels):")
    for r in rows:
        print(f"{r['status']:<9} {r['origin']:<7} score={r['score']:<3} "
              f"subs={r['subscribers'] or '-':<10} @{r['channel']:<28} "
              f"last={r['last_post_at'] or '-'}")
    print(json.dumps(ch.counts(), ensure_ascii=False))
    return 0


def cmd_batch(args):
    queries = [str(q) for q in args.query if str(q).strip()]
    out = orchestrator.run_many(queries, live=args.live, limit=args.limit)
    for r in out.get("runs") or []:
        print(f"\n===== QUERY: {r.get('query')} (ok={r.get('ok')} blocked={r.get('blocked')}) =====")
        print(r.get("report", {}).get("markdown") or f"REPORT FAILED: {r.get('error')}")
    print("\n--- BATCH SUMMARY ---")
    print(json.dumps({"ok": out.get("ok"), "count": out.get("count"),
                      "errors": [r.get("error") for r in out.get("runs") or []
                                  if not r.get("ok")]}, ensure_ascii=False))
    return 0 if out.get("ok") else 1


def cmd_bot(args):
    from . import telegram_bot as tb
    cfg = config.load()
    token = str(cfg.get("telegram_bot_token") or "")
    if not token:
        print("Bot token config me nahi hai. /api/settings ya data/config.json me daayein.")
        return 1
    print("Telegram bot chal raha hai (long polling). Rokne ke liye Ctrl+C.")
    import threading
    stop = threading.Event()
    try:
        tb.run(token, cfg=cfg, stop=stop)
    except KeyboardInterrupt:
        stop.set()
    return 0


def cmd_watchdog(args):
    from . import watchdog
    return watchdog.main(interval=getattr(args, "interval", 10),
                         max_backoff=getattr(args, "max_backoff", 300))


def build_parser():
    p = argparse.ArgumentParser(prog="jin_agent", description="JIN Agent local CLI")
    sub = p.add_subparsers(dest="command")
    sub.add_parser("status").set_defaults(fn=cmd_status)
    r = sub.add_parser("run"); r.add_argument("query", nargs="+")
    r.add_argument("--live", action="store_true"); r.add_argument("--days", type=int, default=7)
    r.add_argument("--limit", type=int, default=25); r.add_argument("--no-save", action="store_true")
    r.set_defaults(fn=cmd_run)
    s = sub.add_parser("search"); s.add_argument("query"); s.add_argument("--limit", type=int, default=20)
    s.set_defaults(fn=cmd_search)
    sub.add_parser("sources").set_defaults(fn=cmd_sources)
    sub.add_parser("digest").set_defaults(fn=cmd_digest)
    e = sub.add_parser("eval"); e.add_argument("--live", action="store_true")
    e.set_defaults(fn=cmd_eval)
    sc = sub.add_parser("schedule"); sc.add_argument("--live", action="store_true")
    sc.add_argument("--poll", type=int, default=20); sc.set_defaults(fn=cmd_schedule)
    sv = sub.add_parser("serve"); sv.add_argument("--port", type=int, default=8766)
    sv.add_argument("--open", action="store_true"); sv.set_defaults(fn=cmd_serve)
    sub.add_parser("selftest").set_defaults(fn=cmd_selftest)
    c = sub.add_parser("classify"); c.add_argument("text"); c.set_defaults(fn=cmd_classify)
    sub.add_parser("llm").set_defaults(fn=cmd_llm)
    cg = sub.add_parser("ci-gate", help="Offline CI gate: compile + tests + eval")
    cg.add_argument("--queries", type=int, default=3, help="evaluator quick check size")
    cg.add_argument("--skip-tests", action="store_true",
                    help="debug only: unittest suite skip (release gate me na lagayein)")
    cg.set_defaults(fn=cmd_ci_gate)
    b = sub.add_parser("batch", help="Parallel agents: multiple queries ek saath")
    b.add_argument("query", nargs="+")
    b.add_argument("--live", action="store_true")
    b.add_argument("--limit", type=int, default=25)
    b.set_defaults(fn=cmd_batch)
    cg2 = sub.add_parser("changes", help="Per-source change detection (snapshots)")
    cg2.add_argument("--limit", type=int, default=20)
    cg2.set_defaults(fn=cmd_changes)
    bt = sub.add_parser("bot", help="Telegram bot long-polling front-end")
    bt.set_defaults(fn=cmd_bot)
    wd = sub.add_parser("watchdog", help="Bot supervisor: crash par auto-restart")
    wd.add_argument("--interval", type=int, default=10)
    wd.add_argument("--max-backoff", type=int, default=300)
    wd.set_defaults(fn=cmd_watchdog)
    chp = sub.add_parser("channels", help="Telegram channel registry (auto-discovery)")
    chp.add_argument("--add", help="manual channel add (@handle ya URL)")
    chp.add_argument("--remove", help="channel archive karo (delete nahi)")
    chp.add_argument("--check", help="liveness probe: '*' ya comma-separated handles")
    chp.add_argument("--discover", action="store_true", help="ek discovery cycle chalao")
    chp.add_argument("--offline", action="store_true", help="discovery offline (sirf harvest)")
    chp.add_argument("--status", help="sirf ye status dikhao (active/dead/archived)")
    chp.set_defaults(fn=cmd_channels)
    return p


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not getattr(args, "command", None):
        parser.print_help()
        return 0
    if args.command == "run":
        args.query = " ".join(args.query)
    store.init_db()
    try:
        return int(args.fn(args) or 0)
    except KeyboardInterrupt:
        print("\nBand kiya gaya.")
        return 130
    except Exception as exc:
        print(f"ERROR {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
