"""MobileLab local HTTP server (Python standard library only)."""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
import urllib.parse
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "web")
sys.path.insert(0, BASE)

import db            # noqa: E402
import firmware      # noqa: E402
import knowledge     # noqa: E402
import research      # noqa: E402
import sahulat       # noqa: E402

VERSION = "1.1.0"
PORT = int(os.environ.get("MOBILELAB_PORT", "8765"))

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".ico": "image/x-icon", ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8"}


class Handler(BaseHTTPRequestHandler):
    server_version = "MobileLab/" + VERSION

    def log_message(self, fmt, *args):
        if os.environ.get("MOBILELAB_VERBOSE"):
            super().log_message(fmt, *args)

    # ------------------------------------------------------------------ helpers
    def _send(self, code: int, body: bytes, ctype: str, extra: dict | None = None):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        for k, v in (extra or {}).items():
            self.send_header(k, v)
        self.end_headers()
        try:
            self.wfile.write(body)
        except (BrokenPipeError, ConnectionResetError):
            pass

    def _json(self, obj, code: int = 200):
        self._send(code, json.dumps(obj, ensure_ascii=False, default=str).encode("utf-8"),
                   "application/json; charset=utf-8")

    def _err(self, msg: str, code: int = 400):
        self._json({"error": msg}, code)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
            if not n:
                return {}
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception:
            return {}

    def _query(self) -> dict:
        return {k: v[0] for k, v in urllib.parse.parse_qs(
            urllib.parse.urlparse(self.path).query, keep_blank_values=True).items()}

    # ------------------------------------------------------------------ routing
    def do_GET(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            if path in ("/", "/index.html"):
                return self._static("index.html")
            if path in ("/app.js", "/style.css", "/favicon.svg"):
                return self._static(path.lstrip("/"))
            if not path.startswith("/api/"):
                return self._err("Not found", 404)
            return self._api_get(path)
        except Exception as e:
            traceback.print_exc()
            return self._err(f"Server error: {e}", 500)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            return self._api_post(path, self._body())
        except Exception as e:
            traceback.print_exc()
            return self._err(f"Server error: {e}", 500)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            m = __import__("re").match(r"/api/packages/(\d+)$", path)
            if not m:
                return self._err("Not found", 404)
            pid = int(m.group(1))
            if not db.one("SELECT id FROM packages WHERE id=?", (pid,)):
                return self._err("Package nahi mila", 404)
            db.execute("DELETE FROM package_files WHERE package_id=?", (pid,))
            db.execute("DELETE FROM packages WHERE id=?", (pid,))
            return self._json({"ok": True, "deleted": pid})
        except Exception as e:
            return self._err(str(e), 500)

    def _static(self, name: str):
        full = os.path.join(WEB, name)
        if not os.path.isfile(full):
            return self._err("File missing: " + name, 404)
        ext = os.path.splitext(name)[1].lower()
        with open(full, "rb") as f:
            self._send(200, f.read(), MIME.get(ext, "application/octet-stream"))

    # ------------------------------------------------------------------ GET API
    def _api_get(self, path: str):
        q = self._query()

        if path == "/api/status":
            s = db.get_settings()
            return self._json({
                "app": "MobileLab", "version": VERSION,
                "python": sys.version.split()[0],
                "db": db.DB_PATH, "web": "http://127.0.0.1:%d" % PORT,
                "counts": db.counts(), "sources": len(research.ALL_SOURCES),
                "policy": sahulat.POLICY["name"], "policy_id": sahulat.POLICY_ID,
                "settings": {k: (("***" if k == "llm_key" and s.get(k) else s.get(k, ""))) for k in s},
                "security_note": knowledge.SECURITY_NOTE,
            })

        if path == "/api/knowledge":
            return self._json({
                "boundary": knowledge.BOUNDARY,
                "official_routes": knowledge.OFFICIAL_ROUTES,
                "tool_arch": knowledge.TOOL_ARCH,
                "glossary": [{"term": a, "def": b} for a, b in knowledge.GLOSSARY],
                "help": [{"title": a, "body": b} for a, b in knowledge.HELP],
                "security_note": knowledge.SECURITY_NOTE,
            })

        if path == "/api/sources":
            return self._json({
                "sources": research.ALL_SOURCES,
                "presets": research.PRESETS,
                "categories": [{"id": k, "label": v} for k, v in research.CATEGORY_LABELS.items()],
            })

        if path == "/api/research":
            params = {
                "q": q.get("q", ""), "preset": q.get("preset", "all"),
                "category": q.get("category", "all"), "exclude": q.get("exclude", ""),
                "days": q.get("days", "0"), "min_score": q.get("min_score", "0"),
                "limit": q.get("limit", "70"), "refresh": q.get("refresh", "0") in ("1", "true", "yes"),
            }
            if q.get("sources"):
                params["sources"] = [x for x in q["sources"].split(",") if x]
            settings = db.get_settings()
            result = research.research(params, settings)
            if result["items"]:
                db.upsert_articles(result["items"])
                guids = [i["guid"] for i in result["items"]]
                marks = db.rows("SELECT guid,saved,is_read FROM articles WHERE guid IN (%s)" %
                                ",".join("?" * len(guids)), tuple(guids))
                mm = {m["guid"]: m for m in marks}
                for i in result["items"]:
                    m = mm.get(i["guid"], {})
                    i["saved"] = bool(m.get("saved"))
                    i["is_read"] = bool(m.get("is_read"))
            result["counts"] = db.counts()
            return self._json(result)

        if path == "/api/articles":
            mode = q.get("mode", "saved")
            if mode == "saved":
                items = db.rows("SELECT * FROM articles WHERE saved=1 ORDER BY fetched_at DESC LIMIT 150")
            else:
                items = db.rows("SELECT * FROM articles ORDER BY fetched_at DESC LIMIT 100")
            return self._json({"items": items})

        if path == "/api/packages":
            return self._json({"items": db.rows(
                "SELECT id,name,path,oem,model,platform,chipset,storage,file_count,total_size,health,tags,created_at "
                "FROM packages ORDER BY created_at DESC")})

        m = __import__("re").match(r"/api/packages/(\d+)$", path)
        if m:
            p = db.package_detail(int(m.group(1)))
            if not p:
                return self._err("Package nahi mila", 404)
            dup = []
            for f in p["files"]:
                for d in db.duplicate_files(f.get("fingerprint", ""), p["id"]):
                    dup.append({"file": f["relpath"], **d})
            p["duplicates"] = dup[:30]
            return self._json(p)

        if path == "/api/models":
            return self._json({"items": db.rows("SELECT * FROM models ORDER BY updated_at DESC")})

        if path == "/api/model-brief":
            term = (q.get("q") or "").strip()
            if not term:
                return self._json({"error": "Model likhein"}, 400)
            card = db.one("SELECT * FROM models WHERE model LIKE ?", ("%" + term + "%",))
            rel = db.rows("SELECT id,name,model,platform,chipset,storage,health FROM packages "
                          "WHERE model LIKE ? OR path LIKE ? ORDER BY created_at DESC LIMIT 10",
                          ("%" + term + "%", "%" + term + "%"))
            live = None
            if q.get("live", "1") in ("1", "true", "yes"):
                try:
                    live = research.research({
                        "q": term, "preset": "all", "category": "all", "limit": 12,
                        "sources": ["gnews", "gsmarena", "xda", "sammobile"], "min_score": 0,
                    }, db.get_settings())
                    live = {"items": live["items"][:10], "fetched_at": live["fetched_at"],
                            "diagnostics": live["diagnostics"]}
                except Exception as e:
                    live = {"error": str(e)[:180]}
            return self._json({"term": term, "card": card, "packages": rel, "live": live,
                               "official": knowledge.OFFICIAL_ROUTES})

        if path == "/api/jobs":
            return self._json({"items": db.rows("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 200")})

        if path == "/api/settings":
            s = db.get_settings()
            if s.get("llm_key"):
                s["llm_key"] = "***"
            return self._json(s)

        # ---- Sahulat & Safe Service Toolkit (PHASE 1B) ----
        if path == "/api/sahulat/overview":
            return self._json(sahulat.overview())

        if path == "/api/sahulat/cases":
            return self._json({"items": db.list_cases(q.get("limit", "200"))})

        if path == "/api/sahulat/check":
            return self._json(sahulat.check_request(q.get("q", "")))

        return self._err("Unknown API: " + path, 404)

    # ------------------------------------------------------------------ POST API
    def _api_post(self, path: str, b: dict):
        if path == "/api/scan":
            raw = (b.get("path") or "").strip().strip('"')
            if not raw:
                return self._err("Folder path likhein.", 400)
            scan = firmware.scan_folder(raw)
            report = firmware.validate(scan)
            pid = db.save_package(scan, report, name=b.get("name", ""),
                                  tags=b.get("tags", ""), notes=b.get("notes", ""))
            return self._json({"ok": True, "id": pid, "report": report,
                               "meta": scan["meta"], "file_count": len(scan["files"])})

        if path == "/api/article":
            guid = (b.get("guid") or "").strip()
            act = b.get("action", "save")
            if not guid:
                return self._err("guid chahiye", 400)
            col, val = ("saved", 1) if act in ("save", "unread") else ("saved", 0)
            if act in ("read", "unread"):
                col, val = ("is_read", 1 if act == "read" else 0)
            if act == "unsave":
                col, val = ("saved", 0)
            db.execute(f"UPDATE articles SET {col}=? WHERE guid=?", (val, guid))
            return self._json({"ok": True, "guid": guid, "action": act})

        if path == "/api/models":
            model = (b.get("model") or "").strip()
            if not model:
                return self._err("Model number zaroori hai", 400)
            db.execute(
                """INSERT INTO models(model,oem,chipset,platform,storage,official_url,notes,updated_at)
                   VALUES(?,?,?,?,?,?,?,?)
                   ON CONFLICT(model) DO UPDATE SET
                     oem=excluded.oem, chipset=excluded.chipset, platform=excluded.platform,
                     storage=excluded.storage, official_url=excluded.official_url,
                     notes=excluded.notes, updated_at=excluded.updated_at""",
                (model, b.get("oem", ""), b.get("chipset", ""), b.get("platform", ""),
                 b.get("storage", ""), b.get("official_url", ""), b.get("notes", ""), time.time()))
            return self._json({"ok": True})

        if path == "/api/jobs":
            if not (b.get("imei") or "").strip() and not (b.get("model") or "").strip():
                return self._err("Kam az kam IMEI ya model likhein", 400)
            db.execute(
                "INSERT INTO jobs(imei,model,customer,proof_ok,route,notes,created_at) VALUES(?,?,?,?,?,?,?)",
                (b.get("imei", ""), b.get("model", ""), b.get("customer", ""),
                 1 if b.get("proof_ok") else 0, b.get("route", ""), b.get("notes", ""), time.time()))
            return self._json({"ok": True})

        if path == "/api/settings":
            data = dict(b)
            if data.get("llm_key") == "***":
                data.pop("llm_key")
            return self._json({"ok": True, "settings": db.set_settings(data)})

        # ---- Sahulat & Safe Service Toolkit (PHASE 1B) ----
        if path == "/api/sahulat/letter":
            try:
                lang = str(b.get("lang") or "roman").strip().lower()
                text = sahulat.make_letter(b, lang)
                return self._json({"ok": True, "lang": lang, "letter": text,
                                   "policy": sahulat.POLICY_ID, "case_no": "(draft)"})
            except ValueError as e:
                return self._err(str(e), 400)

        if path == "/api/sahulat/case":
            # A case is always saved with consent; letter is generated from the SAME data.
            cleaned, errors = sahulat.validate_case(b)
            if errors:
                return self._err("; ".join(errors), 400)
            cleaned["case_no"] = sahulat.make_case_no()
            cleaned["status"] = "ready" if cleaned["proof_ok"] else "draft"
            row = db.add_case(cleaned)
            letter = ""
            letter_error = ""
            try:
                letter = sahulat.make_letter({**cleaned}, str(b.get("lang") or "roman").strip().lower())
            except ValueError as e:
                letter_error = str(e)
            return self._json({"ok": True, "case": row, "letter": letter,
                               "letter_error": letter_error, "policy": sahulat.POLICY_ID})

        if path == "/api/sahulat/check":
            return self._json(sahulat.check_request(b.get("q", "")))

        if path == "/api/reveal":
            target = (b.get("path") or "").strip()
            if not target or not os.path.exists(target):
                return self._err("Path maujood nahi hai", 400)
            allowed = os.path.abspath(target).lower().startswith(BASE.lower()) or bool(
                db.one("SELECT id FROM packages WHERE path=?", (os.path.abspath(target),)))
            if not allowed:
                return self._err("Sirf scanned packages ya workspace folder khol sakte hain", 403)
            try:
                os.startfile(os.path.abspath(target))  # Windows Explorer
                return self._json({"ok": True})
            except Exception as e:
                return self._err(str(e), 500)

        return self._err("Unknown API: " + path, 404)


def main():
    db.init()
    srv = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    url = f"http://127.0.0.1:{PORT}"
    print("=" * 66)
    print("  MobileLab  v" + VERSION + "  -  Local Mobile Software Workbench")
    print("  URL      : " + url)
    print("  Database : " + db.DB_PATH)
    print("  Band karna: is window mein Ctrl+C ya window close")
    print("=" * 66)
    if "--no-browser" not in sys.argv:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        print("\nMobileLab band ho gaya.")
    finally:
        srv.server_close()


if __name__ == "__main__":
    main()
