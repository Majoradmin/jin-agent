"""Loopback-only Agent Console (P20). Python stdlib http.server, light theme.

No CORS, no external assets, no authentication surface: the server binds to
127.0.0.1 only. Secrets are never returned by any endpoint.
"""

from __future__ import annotations

import json
import os
import re
import urllib.parse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from . import (alerts, config, evaluator, llm, orchestrator, policy,
               scheduler, store, util)

WEB = Path(__file__).resolve().parent / "web"
MAX_BODY = 1024 * 1024
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; "
       "img-src 'self' data:; connect-src 'self'; form-action 'self'; "
       "base-uri 'self'; frame-ancestors 'none'")

_SCHEDULER: scheduler.Scheduler | None = None


class Handler(BaseHTTPRequestHandler):
    server_version = "JINAgent/2.0"

    def log_message(self, fmt, *args):
        if os.environ.get("JIN_AGENT_VERBOSE"):
            super().log_message(fmt, *args)

    def _headers(self, extra=None):
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
        for key, value in (extra or {}).items():
            self.send_header(key, value)

    def _json(self, data, code: int = 200):
        body = json.dumps(data, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(code)
        self._headers({"Content-Length": str(len(body))})
        self.end_headers()
        self.wfile.write(body)

    def _err(self, message: str, code: int = 400):
        self._json({"ok": False, "error": message}, code)

    def _static(self, name: str):
        path = WEB / name
        if not path.is_file():
            return self._err("Not found", 404)
        types = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".svg": "image/svg+xml"}
        body = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", types.get(path.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(body)

    def _body(self) -> dict:
        try:
            length = int(self.headers.get("Content-Length") or 0)
        except ValueError:
            return {}
        if length <= 0:
            return {}
        if length > MAX_BODY:
            raise ValueError("Body 1 MiB se bara hai")
        raw = self.rfile.read(length).decode("utf-8", "replace")
        try:
            data = json.loads(raw)
        except ValueError:
            return {}
        return data if isinstance(data, dict) else {}

    def do_GET(self):
        parsed = urllib.parse.urlsplit(self.path)
        path, q = parsed.path, urllib.parse.parse_qs(parsed.query)
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path in ("/app.js", "/style.css", "/favicon.svg"):
                return self._static(path.lstrip("/"))
            if path == "/api/status":
                store.init_db()
                return self._json(orchestrator.status())
            if path == "/api/sources":
                store.init_db()
                return self._json({"ok": True, "sources": store.list_sources(),
                                   "register_size": len(policy.register())})
            if path == "/api/archive":
                store.init_db()
                return self._json({"ok": True, "items": store.search_archive(
                    q.get("q", [""])[0], util.clamp(q.get("limit", [30])[0], 1, 200, 30),
                    q.get("category", ["all"])[0])})
            if path == "/api/watchlist":
                store.init_db()
                return self._json({"ok": True, "items": store.list_watchlist()})
            if path == "/api/reports":
                store.init_db()
                return self._json({"ok": True, "items": store.list_reports()})
            if path == "/api/report":
                store.init_db()
                rec = store.get_report(util.clamp(q.get("id", [0])[0], 1, 10**9, 0))
                if not rec:
                    return self._err("Report nahi mili", 404)
                return self._read_report(rec)
            if path == "/api/overview":
                store.init_db()
                return self._json({"ok": True, "overview": store.overview()})
            if path == "/api/events":
                store.init_db()
                return self._json({"ok": True, "items": store.list_events()})
            if path == "/api/jobs":
                store.init_db()
                return self._json({"ok": True, "items": store.list_jobs()})
            if path == "/api/runs":
                store.init_db()
                return self._json({"ok": True, "items": store.list_runs()})
            if path == "/api/settings":
                return self._json({"ok": True, "settings": config.public()})
            if path == "/api/scheduler":
                return self._json({"ok": True, "state": _scheduler_state()})
            if path == "/api/tools":
                from . import planner
                return self._json({"ok": True, "tools": planner.TOOL_NAMES})
            return self._err("Not found", 404)
        except Exception as exc:
            return self._err(f"{type(exc).__name__}: {util.truncate(str(exc), 160)}", 500)

    def _read_report(self, rec: dict):
        root = os.path.realpath(str(config.reports_dir()))
        target = os.path.realpath(str(rec.get("path") or ""))
        if os.path.commonpath([root, target]) != root or not os.path.isfile(target):
            return self._err("Report path authorized nahi", 403)
        text = Path(target).read_text(encoding="utf-8", errors="replace")[:400_000]
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(text.encode("utf-8"))))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy", CSP)
        self.end_headers()
        self.wfile.write(text.encode("utf-8"))

    def do_POST(self):
        path = urllib.parse.urlsplit(self.path).path
        try:
            data = self._body()
            if path == "/api/run":
                query = str(data.get("query") or "").strip()
                if not query:
                    return self._err("Query likhein")
                out = orchestrator.run(query, live=bool(data.get("live")),
                                       days=util.clamp(data.get("days"), 1, 90, 7),
                                       limit=util.clamp(data.get("limit"), 1, 100, 25),
                                       save=bool(data.get("save", True)))
                return self._json(out)
            if path == "/api/eval/run":
                return self._json({"ok": True, "result": evaluator.run(
                    live=bool(data.get("live")), save=True)})
            if path == "/api/watchlist":
                store.init_db()
                return self._json({"ok": True, "item": store.add_watchlist(
                    data.get("term", ""), data.get("category", "Custom Watchlist"))})
            if path == "/api/watchlist/remove":
                store.init_db()
                store.remove_watchlist(data.get("term", ""))
                return self._json({"ok": True})
            if path == "/api/feedback":
                store.init_db()
                return self._json({"ok": True, "item": store.add_feedback(
                    data.get("guid", ""), bool(data.get("useful")), data.get("note", ""))})
            if path == "/api/settings":
                allowed = {"topics", "telegram_channels", "telegram_bot_token",
                           "telegram_chat_id", "tor_mode", "llm", "schedule",
                           "retention_days", "default_days", "default_limit"}
                patch = {k: v for k, v in data.items() if k in allowed}
                if patch.get("tor_mode") and patch["tor_mode"] not in policy.TOR_MODES:
                    return self._err("tor_mode sirf links_only / off ho sakta hai")
                if isinstance(patch.get("llm"), dict):
                    prov = str(patch["llm"].get("provider") or "").lower()
                    if prov and prov not in llm.PROVIDERS:
                        return self._err("Model provider ghalat hai")
                return self._json({"ok": True, "settings": config.save(patch)})
            if path == "/api/llm/test":
                return self._json({"ok": True, "result": llm.probe(config.load())})
            if path == "/api/scheduler":
                global _SCHEDULER
                action = str(data.get("action") or "status").lower()
                if action == "start":
                    if _SCHEDULER is None or not _SCHEDULER.is_alive():
                        _SCHEDULER = scheduler.Scheduler(
                            config.load(), offline=bool(data.get("offline", True)))
                        _SCHEDULER.start()
                    return self._json({"ok": True, "state": _scheduler_state()})
                if action == "stop":
                    if _SCHEDULER:
                        _SCHEDULER.stop()
                    return self._json({"ok": True, "state": _scheduler_state()})
                if action == "tick":
                    return self._json({"ok": True, "result": scheduler.tick(
                        config.load(), bool(data.get("offline", True)))})
                return self._json({"ok": True, "state": _scheduler_state()})
            if path == "/api/digest":
                return self._json({"ok": True, "result": orchestrator.digest(config.load())})
            if path == "/api/alert/test":
                return self._json({"ok": True, "result": alerts.notify(
                    str(data.get("text") or "JIN Agent test alert"), config.load())})
            if path == "/api/retention":
                store.init_db()
                return self._json({"ok": True, "result": store.retention(
                    util.clamp(data.get("days"), 1, 3650, 90))})
            if path == "/api/backup":
                store.init_db()
                return self._json({"ok": True, "result": store.backup()})
            if path == "/api/classify":
                return self._json({"ok": True, "gate": policy.classify(data.get("text", ""))})
            return self._err("Not found", 404)
        except ValueError as exc:
            return self._err(str(exc))
        except Exception as exc:
            return self._err(f"{type(exc).__name__}: {util.truncate(str(exc), 160)}", 500)


def _scheduler_state() -> dict:
    if _SCHEDULER is None:
        return {"running": False, "ticks": 0, "poll_seconds": 20}
    return _SCHEDULER.state()


def make_server(port: int = 8766) -> ThreadingHTTPServer:
    store.init_db()
    return ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)


def serve(port: int = 8766, open_browser: bool = False):
    httpd = make_server(port)
    url = f"http://127.0.0.1:{port}"
    print(f"JIN Agent console: {url}")
    if open_browser:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever(poll_interval=0.4)
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
