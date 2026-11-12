"""PHASE 8 shared test harness (Python standard library only).

Owns one FIXED throwaway SQLite DB (already gitignored) and starts an
in-process loopback ``ThreadingHTTPServer`` per test module. State is reset
with SQL ``DELETE FROM ...`` only -- no file creation/deletion from Python.
No live internet (every outbound call is mocked inside the individual tests),
and the production DB is never touched.
"""
from __future__ import annotations

import json
import pathlib
import sys
import threading
import urllib.error
import urllib.request
from http.server import ThreadingHTTPServer

BASE = pathlib.Path(__file__).resolve().parents[1]      # ...\MobileLab
ROOT = BASE.parent                                      # J:\Ai Agent
sys.path.insert(0, str(BASE))

import db            # noqa: E402
import research      # noqa: E402
import server        # noqa: E402

TEST_DB = str(BASE / "data" / "_p8_test.db")
_ORIG_DATA_DIR = db.DATA_DIR
_ORIG_DB_PATH = db.DB_PATH


def reset_db() -> None:
    """Deterministic clean state via SQL only (no file deletion)."""
    for t in ("package_files", "packages", "articles", "models", "jobs", "cases",
              "memory_sources", "memory_telegram", "memory_queries", "memory_problems",
              "memory_reports", "memory_feedback", "memory_entities"):
        db.execute("DELETE FROM " + t)
    db.execute("DELETE FROM settings")
    db.init()                       # re-seed DEFAULT_SETTINGS
    research._CACHE.clear()


def start():
    db.DATA_DIR = str(BASE / "data")
    db.DB_PATH = TEST_DB
    db.init()
    reset_db()
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), server.Handler)
    port = httpd.server_address[1]
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd, port


def stop(httpd) -> None:
    if httpd is not None:
        httpd.shutdown()
        httpd.server_close()
    db.DATA_DIR = _ORIG_DATA_DIR
    db.DB_PATH = _ORIG_DB_PATH


def request(port, path, payload=None, method=None, body=None, headers=None):
    """Return ``(status, headers_dict, raw_body_bytes)`` for a loopback call."""
    url = f"http://127.0.0.1:{port}{path}"
    data = None
    hdrs = dict(headers or {})
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        hdrs.setdefault("Content-Type", "application/json")
        method = method or "POST"
    elif body is not None:
        data = body
        method = method or "POST"
    method = method or "GET"
    req = urllib.request.Request(url, data=data, headers=hdrs, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status, dict(r.headers), r.read()
    except urllib.error.HTTPError as e:
        return e.code, dict(e.headers), e.read()


def get_json(port, path, **kw):
    code, hdrs, raw = request(port, path, **kw)
    return code, hdrs, json.loads(raw.decode("utf-8", "replace"))


def post_json(port, path, payload):
    return get_json(port, path, payload=payload)


def delete_json(port, path):
    return get_json(port, path, method="DELETE")


def header(hdrs, name):
    for k, v in hdrs.items():
        if k.lower() == name.lower():
            return v
    return None
