"""MobileLab local HTTP server (Python standard library only)."""
from __future__ import annotations

import ipaddress
import json
import math
import os
import re
import socket
import sys
import threading
import time
import traceback
import urllib.parse
import urllib.request
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

BASE = os.path.dirname(os.path.abspath(__file__))
WEB = os.path.join(BASE, "web")
sys.path.insert(0, BASE)

import db            # noqa: E402
import agent_memory  # noqa: E402
import firmware      # noqa: E402
import knowledge     # noqa: E402
import research      # noqa: E402
import sahulat       # noqa: E402
import service_brief  # noqa: E402
import telegram_public  # noqa: E402

VERSION = "1.3.0"
PORT = int(os.environ.get("MOBILELAB_PORT", "8765"))

MIME = {".html": "text/html; charset=utf-8", ".js": "application/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8", ".ico": "image/x-icon", ".svg": "image/svg+xml",
        ".json": "application/json; charset=utf-8"}

# ---------------------------------------------------------------------------
# Security constants (P9 / QA #7)
# ---------------------------------------------------------------------------
MAX_BODY = 1024 * 1024                      # ~1 MiB request cap -> 413
CSP = ("default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; connect-src 'self'; object-src 'none'; "
       "base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
WORKSPACE = os.path.realpath(BASE)         # default scan / reveal boundary (C6 / QA #3)

# Bounded research-cache housekeeping (QA #10). research.py owns _CACHE; this
# is a guarded, additive guard so it can never break a request.
_CACHE_MAX = 256
_CACHE_TTL = 24 * 3600

# llm_endpoint SSRF blocklist hostnames (QA #6).
_BLOCKED_HOSTS = {"localhost", "metadata", "metadata.google.internal",
                  "metadata.goog", "instance-data"}


class _BadParam(ValueError):
    """Invalid query parameter -> 400 with a concise Roman Urdu reason."""


class _BodyTooLarge(Exception):
    """Request body over the cap -> 413."""


class _PathDenied(Exception):
    """Path authorization failure -> 4xx (never a stack trace / abs path)."""


# Windows absolute paths / UNC paths must never reach a client in an error.
_ABS_PATH = re.compile(r"(?<![A-Za-z0-9])[A-Za-z]:[\\/][^\s,;'\"]+|\\\\[^\s,;'\"]+")


def _scrub(msg) -> str:
    """Strip stack traces and absolute internal paths from any error reason (QA #11)."""
    text = _ABS_PATH.sub("[path]", str(msg))
    text = " ".join(ln for ln in text.splitlines()
                    if "Traceback" not in ln and not ln.lstrip().startswith("File "))
    return (text.strip() or "Ghalat darkhwast")[:400]


def _log(context: str, exc: BaseException | None = None) -> None:
    """Server-side logging only; never part of an API response (QA #11 / QA #12)."""
    if exc is None:
        print("[MobileLab] " + context, file=sys.stderr)
    else:
        print("[MobileLab] %s: %s: %s" % (context, type(exc).__name__, exc),
              file=sys.stderr)


def _truthy(v) -> bool:
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return v != 0
    if isinstance(v, str):
        return v.strip().lower() in ("1", "true", "yes", "on")
    return False


def _parse_num(raw, *, default, cast, lo=None, hi=None, name="parameter"):
    """Safe numeric parse of a query param (QA #2). Non-numeric -> _BadParam.

    Numeric out-of-range values are clamped (lo/hi); non-numeric / NaN / Inf
    raise so the handler returns 400 JSON instead of an uncaught 500.
    """
    if raw is None or (isinstance(raw, str) and not raw.strip()):
        return cast(default)
    try:
        val = float(raw)
    except (TypeError, ValueError, OverflowError):
        raise _BadParam(f"{name} ghalat hai; sahih number likhein")
    if not math.isfinite(val):
        raise _BadParam(f"{name} ghalat hai; sahih number likhein")
    if lo is not None and hi is not None:
        val = max(lo, min(hi, val))
    return cast(val)


# ---------------------------------------------------------------------------
# Path authorization (QA #3): realpath + commonpath, authorize before exists().
# ---------------------------------------------------------------------------
def _is_unc(p: str) -> bool:
    return p.replace("/", "\\").startswith("\\\\")


def _within(real: str) -> bool:
    try:
        common = os.path.commonpath([real, WORKSPACE])
    except (ValueError, OSError):
        return False                       # different drives / malformed paths
    return os.path.normcase(common) == os.path.normcase(WORKSPACE)


def _authorize_path(raw: str, allow_outside: bool = False, extra=()) -> str:
    """Return realpath if authorized, else raise _PathDenied (before any exists())."""
    if not raw or not isinstance(raw, str):
        raise _PathDenied("Path likhein")
    if _is_unc(raw):
        raise _PathDenied("UNC ya network path ki ijazat nahi hai")
    # QA #7 fix: /api/status no longer exposes an absolute DB path, so the UI
    # offers a RELATIVE sample folder instead. Resolve such paths against BASE
    # (not the process CWD) and strip leading separators to avoid drive-root escapes.
    drive, tail = os.path.splitdrive(raw)
    if not drive:
        raw = os.path.join(BASE, tail.lstrip("\\/"))
    try:
        real = os.path.realpath(raw)
        lex = os.path.abspath(raw)
    except (OSError, ValueError):
        raise _PathDenied("Path ghalat hai")
    # Symlink / junction / '..' escape: lexical inside workspace, resolved outside.
    if _within(lex) and not _within(real):
        raise _PathDenied("Symlink se workspace se bahar jane ki ijazat nahi hai")
    norm_real = os.path.normcase(real)
    norm_lex = os.path.normcase(lex)
    # Legitimate scanned-package paths (revealed after an explicit scan).
    for p in extra:
        try:
            np = os.path.normcase(os.path.abspath(p))
        except (OSError, ValueError):
            continue
        if np in (norm_real, norm_lex):
            return real
    if _within(real) or allow_outside:
        return real
    raise _PathDenied("Workspace se bahar ka folder ijazat nahi hai; "
                      "allow_outside=true chahiye")


# ---------------------------------------------------------------------------
# llm_endpoint SSRF validator (implemented LOCALLY, QA #6).
# ---------------------------------------------------------------------------
def _ip_is_internal(ip_str: str) -> bool:
    try:
        ip = ipaddress.ip_address(ip_str)
    except ValueError:
        return False
    return (ip.is_private or ip.is_loopback or ip.is_link_local or
            ip.is_reserved or ip.is_multicast or ip.is_unspecified)


def _check_endpoint(url: str):
    """Return (ok, Roman Urdu reason). http/https only; block internal hosts/IPs.

    The resolved destination IP is validated with ipaddress + socket. Public
    hostnames are allowed without a live DNS lookup (offline-tolerant), so a
    valid configured endpoint is never blocked just because DNS is unavailable.
    """
    if not url:
        return True, ""                    # empty endpoint = feature disabled
    if not isinstance(url, str):
        return False, "Endpoint ghalat hai"
    parsed = urllib.parse.urlparse(url.strip())
    if parsed.scheme not in ("http", "https"):
        return False, "Sirf http/https endpoint ki ijazat hai"
    if parsed.username or parsed.password:
        return False, "Endpoint mein credentials ki ijazat nahi hai"
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        return False, "Endpoint host ghalat hai"
    if host in _BLOCKED_HOSTS or host.endswith(".localhost") or host.endswith(".internal"):
        return False, "Internal endpoint ki ijazat nahi hai"
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    try:
        ip = ipaddress.ip_address(host)
        is_literal = True
    except ValueError:
        is_literal = False
    if is_literal:
        # Validate the literal AND its resolved addresses (no DNS needed).
        try:
            resolved = [i[4][0] for i in socket.getaddrinfo(host, port)]
        except (socket.gaierror, OSError, ValueError):
            resolved = [host]
        for addr in resolved:
            if _ip_is_internal(addr):
                return False, "Internal IP endpoint ki ijazat nahi hai"
        return True, ""
    # Non-literal public hostname: no live DNS (offline app); allow it.
    return True, ""


def validate_llm_endpoint(url: str) -> bool:
    """Public local SSRF validator. True = endpoint allowed."""
    return _check_endpoint(url)[0]


# Neutral aliases so callers can reach the local validator by a generic name.
validate_endpoint = validate_llm_endpoint
is_safe_endpoint = validate_llm_endpoint


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None                        # redirects disabled (QA #6)


def build_no_redirect_opener():
    """urllib.request opener with redirects disabled (QA #6)."""
    return urllib.request.build_opener(_NoRedirect)


def _safe_settings(s: dict) -> dict:
    """Point-of-use guard: never send the optional LLM request to an internal host."""
    out = dict(s)
    ep = (out.get("llm_endpoint") or "").strip()
    if ep:
        ok, reason = _check_endpoint(ep)
        if not ok:
            _log("llm_endpoint SSRF blocked: " + reason)   # QA #12: not swallowed
            out["llm_endpoint"] = ""       # disable the outbound LLM rewrite
    return out


def _prune_research_cache():
    """Keep research._CACHE bounded (LRU + TTL). Guarded: research.py owns it."""
    try:
        cache = getattr(research, "_CACHE", None)
        if not isinstance(cache, dict):
            return
        now = time.time()
        for k, v in list(cache.items()):
            ts = v[0] if isinstance(v, tuple) and v and isinstance(v[0], (int, float)) else None
            if ts is None or now - ts > _CACHE_TTL:
                cache.pop(k, None)
        while len(cache) > _CACHE_MAX:
            try:
                oldest = min(cache, key=lambda k: cache[k][0]
                             if isinstance(cache[k], tuple) and cache[k] else 0)
            except Exception:
                break
            cache.pop(oldest, None)
    except Exception:
        pass                              # housekeeping must never break a request


def _mask_settings(s: dict) -> dict:
    """Never echo a plaintext llm_key; keep the '***' indicator (QA #1)."""
    out = dict(s)
    if out.get("llm_key"):
        out["llm_key"] = "***"
    return out


# Strict action -> (parameterized SQL, value) allowlist (QA #8).
_ARTICLE_UPDATES = {
    "save":   ("UPDATE articles SET saved=? WHERE guid=?", 1),
    "unsave": ("UPDATE articles SET saved=? WHERE guid=?", 0),
    "read":   ("UPDATE articles SET is_read=? WHERE guid=?", 1),
    "unread": ("UPDATE articles SET is_read=? WHERE guid=?", 0),
}


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
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Content-Security-Policy", CSP)
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
        self._json({"error": _scrub(msg)}, code)

    def _body(self) -> dict:
        try:
            n = int(self.headers.get("Content-Length") or 0)
        except (TypeError, ValueError):
            n = 0
        if n < 0:
            n = 0
        if n > MAX_BODY:
            # Drain the rejected body so the connection closes cleanly (no RST),
            # otherwise the client cannot read the 413 JSON error.
            remaining = n
            while remaining > 0:
                chunk = self.rfile.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
            raise _BodyTooLarge()
        if not n:
            return {}
        try:
            return json.loads(self.rfile.read(n).decode("utf-8"))
        except Exception as e:
            _log("malformed JSON body", e)  # QA #12: log, don't silently swallow
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
        except _BadParam as e:
            return self._err(str(e), 400)
        except _BodyTooLarge:
            return self._err("Request body bohat bara hai", 413)
        except _PathDenied as e:
            return self._err(str(e), 403)
        except Exception:
            traceback.print_exc()         # server-side only (QA #11)
            return self._err("Server mein masla aaya; dobara koshish karein", 500)

    def do_POST(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            return self._api_post(path, self._body())
        except _BodyTooLarge:
            return self._err("Request body bohat bara hai", 413)
        except _BadParam as e:
            return self._err(str(e), 400)
        except _PathDenied as e:
            return self._err(str(e), 400)
        except Exception:
            traceback.print_exc()
            return self._err("Server mein masla aaya; dobara koshish karein", 500)

    def do_DELETE(self):
        path = urllib.parse.urlparse(self.path).path
        try:
            m = re.match(r"/api/packages/(\d+)$", path)
            if m:
                pid = int(m.group(1))
                if not db.one("SELECT id FROM packages WHERE id=?", (pid,)):
                    return self._err("Package nahi mila", 404)
                db.execute("DELETE FROM package_files WHERE package_id=?", (pid,))
                db.execute("DELETE FROM packages WHERE id=?", (pid,))
                return self._json({"ok": True, "deleted": pid})
            m = re.match(r"/api/memory/sources/(\d+)$", path)
            if m:
                try:
                    row = agent_memory.archive_source(int(m.group(1)))
                except ValueError as e:
                    return self._err(str(e), 404)
                return self._json({"ok": True, "archived": True, "source": row})
            m = re.match(r"/api/memory/telegram/(\d+)$", path)
            if m:
                try:
                    row = agent_memory.archive_telegram(int(m.group(1)))
                except ValueError as e:
                    return self._err(str(e), 404)
                return self._json({"ok": True, "archived": True, "telegram": row})
            return self._err("Not found", 404)
        except _BadParam as e:
            return self._err(str(e), 400)
        except Exception:
            traceback.print_exc()
            return self._err("Server mein masla aaya; dobara koshish karein", 500)

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
                "db": os.path.basename(db.DB_PATH),   # QA #7: no absolute DB path
                "sample_dir": os.path.join("samples", "MTK_Demo_MT6899_UFS"),  # relative hint only
                "web": "http://127.0.0.1:%d" % PORT,
                "counts": db.counts(), "sources": len(research.ALL_SOURCES),
                "policy": sahulat.POLICY["name"], "policy_id": sahulat.POLICY_ID,
                "settings": _mask_settings(s),
                "security_note": knowledge.SECURITY_NOTE,
                "service_brief_version": service_brief.VERSION,
                "service_brief_sources": len(service_brief.SOURCES),
                "memory_version": agent_memory.VERSION,
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
            # QA #2: validate all numeric query params before research parses them.
            days = _parse_num(q.get("days"), cast=int, default=0,
                              lo=0, hi=3650, name="days")
            min_score = _parse_num(q.get("min_score"), cast=float, default=0.0,
                                   name="min_score")
            limit = _parse_num(q.get("limit"), cast=int, default=70,
                               lo=5, hi=200, name="limit")
            params = {
                "q": q.get("q", ""), "preset": q.get("preset", "all"),
                "category": q.get("category", "all"), "exclude": q.get("exclude", ""),
                "days": days, "min_score": min_score, "limit": limit,
                "refresh": q.get("refresh", "0") in ("1", "true", "yes"),
            }
            if q.get("sources"):
                params["sources"] = [x for x in q["sources"].split(",") if x]
            preset_q = next((p["q"] for p in research.PRESETS
                             if p["id"] == params["preset"]), "")
            recall_q = params["q"] or preset_q
            try:
                recall = agent_memory.recall(recall_q, params["category"])
            except Exception as e:
                _log("memory recall", e)
                recall = {"known": False, "queries": [], "problems": [],
                          "sources": [], "message": ""}
            settings = _safe_settings(db.get_settings())
            result = research.research(params, settings)
            _prune_research_cache()
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
            try:
                saved = agent_memory.record_research(params, result)
            except Exception as e:
                _log("memory record", e)
                saved = None
            result["memory"] = {"recall": recall, "saved": saved}
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
            cols = ("SELECT id,name,path,oem,model,platform,chipset,storage,file_count,"
                    "total_size,health,tags,created_at FROM packages")
            total = db.one("SELECT COUNT(*) n FROM packages")["n"]
            if q.get("limit") is not None or q.get("offset") is not None:
                lim = _parse_num(q.get("limit"), cast=int, default=25,
                                 lo=1, hi=200, name="limit")
                off = _parse_num(q.get("offset"), cast=int, default=0,
                                 lo=0, hi=10 ** 9, name="offset")
                items = db.rows(cols + " ORDER BY created_at DESC LIMIT ? OFFSET ?",
                                (lim, off))
                page = off // lim + 1
                pages = max(1, math.ceil(total / lim))
            else:
                items = db.rows(cols + " ORDER BY created_at DESC")
                page, pages = 1, 1
            # additive fields only -> frontend keeps working unchanged (QA #10)
            return self._json({"items": items, "total": total,
                               "page": page, "pages": pages})

        m = re.match(r"/api/packages/(\d+)$", path)
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
                    }, _safe_settings(db.get_settings()))
                    live = {"items": live["items"][:10], "fetched_at": live["fetched_at"],
                            "diagnostics": live["diagnostics"]}
                except Exception as e:
                    _log("model-brief live research", e)   # QA #12: log, don't swallow
                    live = {"error": "Live research dastiyab nahi"}
            return self._json({"term": term, "card": card, "packages": rel, "live": live,
                               "official": knowledge.OFFICIAL_ROUTES})

        if path == "/api/jobs":
            return self._json({"items": db.rows("SELECT * FROM jobs ORDER BY created_at DESC LIMIT 200")})

        if path == "/api/settings":
            return self._json(_mask_settings(db.get_settings()))

        # ---- Sahulat & Safe Service Toolkit (PHASE 1B) ----
        if path == "/api/sahulat/overview":
            return self._json(sahulat.overview())

        if path == "/api/sahulat/cases":
            return self._json({"items": db.list_cases(q.get("limit", "200"))})

        if path == "/api/sahulat/check":
            return self._json(sahulat.check_request(q.get("q", "")))

        # ---- Service Brief & Official Status Checks (PHASE 12) ----
        if path == "/api/service-brief/overview":
            return self._json(service_brief.overview())

        if path == "/api/service-brief/classify":
            return self._json(service_brief.classify(q.get("q", "")))

        # ---- Agent memory (P13) ----
        if path == "/api/memory/overview":
            return self._json(agent_memory.overview())

        if path == "/api/memory/sources":
            return self._json({
                "items": agent_memory.list_sources(
                    include_archived=_truthy(q.get("include_archived")),
                    limit=_parse_num(q.get("limit"), cast=int, default=200,
                                     lo=1, hi=500, name="limit")),
            })

        if path == "/api/memory/telegram":
            return self._json({
                "items": agent_memory.list_telegram(
                    include_disabled=_truthy(q.get("include_disabled")),
                    limit=_parse_num(q.get("limit"), cast=int, default=200,
                                     lo=1, hi=500, name="limit")),
            })

        if path == "/api/memory/telegram/search":
            limit = _parse_num(q.get("limit"), cast=int, default=20,
                               lo=1, hi=100, name="limit")
            channel = (q.get("channel") or "").strip()
            if not channel:
                return self._err("Telegram channel likhein", 400)
            try:
                ch = telegram_public.normalize_channel(channel)
            except ValueError as e:
                return self._err(str(e), 400)
            result = telegram_public.fetch_channel(ch, q.get("q", ""), limit)
            agent_memory.touch_telegram(ch, bool(result.get("ok")), result.get("error", ""))
            if result.get("ok") and _truthy(q.get("remember", "1")):
                agent_memory.remember_telegram_if_new(ch)
            return self._json(result)

        if path == "/api/memory/recall":
            return self._json(agent_memory.recall(
                q.get("q", ""), q.get("category", "all"),
                _parse_num(q.get("limit"), cast=int, default=6,
                           lo=1, hi=30, name="limit")))

        if path == "/api/memory/queries":
            limit = _parse_num(q.get("limit"), cast=int, default=50,
                               lo=1, hi=300, name="limit")
            return self._json({"items": db.rows(
                "SELECT * FROM memory_queries ORDER BY updated_at DESC LIMIT ?", (limit,))})

        if path == "/api/memory/problems":
            limit = _parse_num(q.get("limit"), cast=int, default=50,
                               lo=1, hi=300, name="limit")
            return self._json({"items": db.rows(
                "SELECT * FROM memory_problems ORDER BY updated_at DESC LIMIT ?", (limit,))})

        if path == "/api/memory/feedback":
            limit = _parse_num(q.get("limit"), cast=int, default=50,
                               lo=1, hi=300, name="limit")
            return self._json({"items": agent_memory.list_feedback(limit)})

        if path == "/api/memory/markdown":
            body = agent_memory.export_markdown().encode("utf-8")
            return self._send(200, body, "text/markdown; charset=utf-8",
                              {"Content-Disposition": 'inline; filename="agent_memory.md"'})

        return self._err("Unknown API: " + path, 404)

    # ------------------------------------------------------------------ POST API
    def _api_post(self, path: str, b: dict):
        if path == "/api/scan":
            raw = (b.get("path") or "").strip().strip('"')
            if not raw:
                return self._err("Folder path likhein.", 400)
            q = self._query()
            allow_outside = (_truthy(b.get("allow_outside")) or
                             _truthy(q.get("allow_outside")))
            try:
                real = _authorize_path(raw, allow_outside)
            except _PathDenied as e:
                return self._err(str(e), 400)
            try:
                scan = firmware.scan_folder(real)
                report = firmware.validate(scan)
            except ValueError:
                return self._err("Folder maujood nahi hai; sahi path likhein", 400)
            pid = db.save_package(scan, report, name=b.get("name", ""),
                                  tags=b.get("tags", ""), notes=b.get("notes", ""))
            return self._json({"ok": True, "id": pid, "report": report,
                               "meta": scan["meta"], "file_count": len(scan["files"])})

        if path == "/api/article":
            guid = (b.get("guid") or "").strip()
            act = b.get("action", "save")
            if not guid:
                return self._err("guid chahiye", 400)
            if act not in _ARTICLE_UPDATES:
                return self._err("Action ghalat hai", 400)
            sql, val = _ARTICLE_UPDATES[act]
            db.execute(sql, (val, guid))
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
                data.pop("llm_key")        # preserve the stored key on round-trip
            ep = (data.get("llm_endpoint") or "").strip()
            if ep:
                ok, reason = _check_endpoint(ep)
                if not ok:
                    return self._err(reason, 400)   # QA #6: reject internal endpoint
            return self._json({"ok": True, "settings": _mask_settings(db.set_settings(data))})

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

        # ---- Service Brief & Official Status Checks (PHASE 12) ----
        if path == "/api/service-brief/classify":
            return self._json(service_brief.classify(str(b.get("q") or "")))

        if path == "/api/service-brief/status":
            try:
                return self._json(service_brief.build_status_report(b))
            except ValueError as e:
                return self._err(str(e), 400)

        if path == "/api/service-brief/gsx":
            try:
                return self._json(service_brief.build_gsx_worksheet(b))
            except ValueError as e:
                return self._err(str(e), 400)

        if path == "/api/service-brief/problem":
            query = str(b.get("q") or b.get("issue") or "").strip()
            if not query:
                return self._err("Masla / sawaal likhein", 400)
            cls = service_brief.classify(query)
            # A blocked request NEVER triggers a live search: only the official
            # route + reason is returned. This is both safer and network-free.
            result = {"items": [], "diagnostics": [], "sources_ok": 0,
                      "sources_failed": 0, "terms": cls["terms"], "query": query}
            if not cls["blocked"] and _truthy(b.get("live", True)):
                params = {
                    "q": (" ".join(cls["terms"])[:200] or query[:200]),
                    "preset": "all", "category": "all", "exclude": "",
                    "days": 0, "min_score": 0, "limit": 20,
                    "sources": ["gnews", "hn", "github", "gsmarena", "xda",
                                "androidauthority", "sammobile", "apple"],
                    "refresh": False,
                }
                try:
                    result = research.research(params, _safe_settings(db.get_settings()))
                    _prune_research_cache()
                except Exception as e:
                    _log("service-brief research", e)   # QA #12: log, don't swallow
                    result["diagnostics"] = [{"source": "research", "ok": False,
                                              "count": 0,
                                              "error": "Live research dastiyab nahi"}]
                    result["sources_failed"] = 1
            elif cls["blocked"]:
                result["diagnostics"] = [{"source": "policy", "ok": True, "count": 0}]
            try:
                brief = service_brief.build_problem_brief(query, result)
            except ValueError as e:
                return self._err(str(e), 400)
            brief["classification"] = cls
            return self._json(brief)

        if path == "/api/reveal":
            target = (b.get("path") or "").strip()
            if not target:
                return self._err("Path likhein", 400)
            q = self._query()
            allow_outside = (_truthy(b.get("allow_outside")) or
                             _truthy(q.get("allow_outside")))
            try:
                extra = [r["path"] for r in db.rows("SELECT path FROM packages") if r.get("path")]
                real = _authorize_path(target, allow_outside, extra=extra)
            except _PathDenied as e:
                return self._err(str(e), 403)
            # authorize BEFORE existence checks (QA #3)
            if not os.path.exists(real):
                return self._err("Path maujood nahi hai", 400)
            try:
                os.startfile(real)          # Windows Explorer
                return self._json({"ok": True})
            except Exception as e:
                _log("os.startfile", e)
                return self._err("Folder kholne mein masla aaya", 500)

        # ---- Agent memory (P13) ----
        if path == "/api/memory/sources":
            try:
                row = agent_memory.add_source(b)
            except ValueError as e:
                return self._err(str(e), 400)
            return self._json({"ok": True, "source": row})

        if path == "/api/memory/sources/promote":
            try:
                sid = int(b.get("id") or 0)
            except (TypeError, ValueError):
                return self._err("Source id ghalat hai", 400)
            try:
                row = agent_memory.promote_source(sid, _truthy(b.get("useful", True)))
            except ValueError as e:
                return self._err(str(e), 404)
            return self._json({"ok": True, "source": row})

        if path == "/api/memory/telegram":
            try:
                row = agent_memory.add_telegram(b)
            except ValueError as e:
                return self._err(str(e), 400)
            return self._json({"ok": True, "telegram": row})

        if path == "/api/memory/problems":
            try:
                row = agent_memory.add_problem(b)
            except ValueError as e:
                return self._err(str(e), 400)
            return self._json({"ok": True, "problem": row})

        if path == "/api/memory/feedback":
            try:
                row = agent_memory.add_feedback(b)
            except ValueError as e:
                return self._err(str(e), 400)
            return self._json({"ok": True, "feedback": row})

        if path == "/api/memory/report":
            return self._json({"ok": True, "report": agent_memory.save_report(b)})

        if path == "/api/memory/export":
            return self._json(agent_memory.write_markdown())

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
