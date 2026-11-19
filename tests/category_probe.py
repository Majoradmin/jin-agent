#!/usr/bin/env python3
"""JIN Agent — Telegram bot CATEGORY probe (offline, fake Bot API).

Live Telegram ke baghair poora bot end-to-end test: asli `jin_agent.telegram_bot.run()`
ko ek fake Bot API ke saath chalayein aur HAR command category ko ek update bhejein.
Har category ki outbound messages record hoti hain — report milta hai kya bheja gaya.

Chalane ka tareeqa:
    JIN_AGENT_DATA=$(mktemp -d) python3 tests/category_probe.py
    JIN_AGENT_DATA=$(mktemp -d) python3 tests/category_probe.py --live   # /research live

Ye production bot ko chhedta nahi — sirf test harness hai.
"""
from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import jin_agent.config as config          # noqa: E402
import jin_agent.telegram_bot as tb        # noqa: E402

CHAT = 123456
LIVE = "--live" in sys.argv


class FakeAPI:
    """Telegram Bot API ka minimal fake — saari outbound calls record karta hai."""

    def __init__(self) -> None:
        self._updates: list[dict] = []
        self._next_id = 1
        self.calls: list[dict] = []
        self._lock = threading.Lock()

    # ---- inbound (test -> bot) ------------------------------------------------
    def _add(self, payload: dict) -> int:
        with self._lock:
            uid = self._next_id
            self._next_id += 1
            payload["update_id"] = uid
            self._updates.append(payload)
            return uid

    def push(self, text: str) -> int:
        return self._add({
            "message": {
                "message_id": self._next_id, "date": int(time.time()),
                "text": text,
                "chat": {"id": CHAT, "type": "private", "first_name": "Test"},
                "from": {"id": CHAT, "is_bot": False, "first_name": "Test"},
            }
        })

    def push_callback(self, callback_id: str, data: str) -> int:
        return self._add({
            "callback_query": {
                "id": callback_id,
                "from": {"id": CHAT, "is_bot": False, "first_name": "Test"},
                "message": {"message_id": 9000 + self._next_id, "date": int(time.time()),
                            "chat": {"id": CHAT, "type": "private"}},
                "data": data,
            }
        })

    # ---- outbound (bot -> Telegram) ------------------------------------------
    def get_updates(self, offset: int, timeout: int = 30) -> list[dict]:
        if not timeout:                      # startup drain — kuch nahi bhejte
            return []
        with self._lock:
            return [u for u in self._updates if int(u.get("update_id") or 0) >= int(offset)]

    def send(self, chat_id, text, parse_mode=None, **kwargs):
        with self._lock:
            mid = 1000 + len(self.calls)
            self.calls.append({"m": "sendMessage", "chat": chat_id,
                               "parse_mode": parse_mode, "text": str(text),
                               "buttons": kwargs.get("buttons")})
        return {"ok": True, "result": {"message_id": mid}}

    def edit(self, chat_id, mid, text):
        with self._lock:
            self.calls.append({"m": "editMessageText", "chat": chat_id,
                               "mid": mid, "text": str(text)})
        return True

    def answer_callback(self, callback_id, text=""):
        with self._lock:
            self.calls.append({"m": "answerCallbackQuery", "id": callback_id,
                               "text": str(text)})
        return {"ok": True, "result": True}

    def send_document(self, chat_id, file_path, caption="", timeout=120):
        with self._lock:
            self.calls.append({"m": "sendDocument", "chat": chat_id,
                               "file": str(file_path), "caption": str(caption)})
        return {"ok": True, "result": {"message_id": 99999}}

    # ---- helpers --------------------------------------------------------------
    def snapshot(self) -> list[dict]:
        with self._lock:
            return list(self.calls)


CATEGORIES: list[tuple[str, str, int]] = [
    # (category, update text, max wait seconds)
    ("start", "/start", 8),
    ("help", "/help", 8),
    ("status", "/status", 8),
    ("sources", "/sources", 8),
    ("channels", "/channels", 8),
    ("addchannel-confirm", "/addchannel @durov", 8),
    ("addchannel-ok-cb", "__CALLBACK__:add:ok:durov", 8),
    ("addchannel-cancel-cb", "__CALLBACK__:add:no", 8),
    ("rmchannel", "/rmchannel @durov", 8),
    ("tgsearch", "/tgsearch firmware", 15),
    ("engines", "/engines", 8),
    ("deep", "/deep firmware", 8),
    ("memory", "/memory", 10),
    ("explore", "/explore python", 60),
    ("digest", "/digest", 15),
    ("alerts", "/alerts", 8),
    ("reports", "/reports", 8),
    ("schedule", "/schedule", 8),
    ("channelhealth", "/channelhealth", 10),
    ("memoryaudit", "/memoryaudit", 15),
    ("selftest", "/selftest", 20),
    ("new", "/new", 8),
    ("stop", "/stop", 8),
    ("unknown-cmd", "/kuchbhi", 8),
    ("plain-text", "salam", 8),
    ("research", "/research python for beginners", 180),
]


def run_category(fake: FakeAPI, spec: str, wait: int, hold: bool = False) -> list[dict]:
    before = len(fake.snapshot())
    if spec.startswith("__CALLBACK__:"):
        fake.push_callback("cb-" + spec.split(":", 1)[1], spec.split(":", 1)[1])
    else:
        fake.push(spec)

    t0 = time.time()
    last = before
    stable = 0.0
    while time.time() - t0 < wait:
        time.sleep(0.5)
        if hold:                        # research: poora waqt (30-60s+) intezar
            continue
        n = len(fake.snapshot())
        if n > last:
            last = n
            stable = 0.0
        else:
            stable += 0.5
        if n > before and stable >= 4.0:
            break
    return fake.snapshot()[before:]


def main() -> int:
    cfg = config.load()
    cfg["telegram_chat_id"] = str(CHAT)
    fake = FakeAPI()
    stop = threading.Event()

    t = threading.Thread(target=tb.run, kwargs={
        "token": "123456:TEST", "cfg": cfg, "stop": stop, "api": fake,
    }, daemon=True, name="jin-bot-probe")
    t.start()
    time.sleep(2.0)                          # bot ready hone ka intezar

    print("=" * 78)
    print("JIN Agent — Telegram category probe  (live=%s)" % LIVE)
    print("data dir:", cfg.get("data_dir") or os.environ.get("JIN_AGENT_DATA"))
    print("=" * 78)

    rows = []
    for cat, spec, wait in CATEGORIES:
        if cat == "research" and not LIVE:
            rows.append((cat, spec, [], "SKIP (--live na diya)"))
            print(f"[{cat:20s}] SKIP")
            continue
        try:
            calls = run_category(fake, spec, wait,
                                 hold=(cat in ("research", "addchannel-ok-cb")))
        except Exception as exc:
            rows.append((cat, spec, [], f"PROBE ERROR {type(exc).__name__}: {exc}"))
            print(f"[{cat:20s}] PROBE ERROR {exc}")
            continue
        first = calls[0]["text"].replace("\n", " ")[:70] if calls else "(koi message nahi)"
        rows.append((cat, spec, calls, first))
        methods = ",".join(sorted({c["m"] for c in calls}))
        print(f"[{cat:20s}] {len(calls):2d} msg  [{methods}]  {first}")

    stop.set()
    time.sleep(1.0)

    print()
    print("=" * 78)
    print("SUMMARY")
    print("=" * 78)
    ok = sum(1 for r in rows if r[2])
    print(f"categories tested : {len(rows)}")
    print(f"koi message aaya  : {ok}")
    print(f"khali (FAIL)      : {len(rows) - ok}")
    print()
    for cat, spec, calls, note in rows:
        status = "OK " if calls else ("SKIP" if "SKIP" in note else "FAIL")
        print(f"  {status}  {cat:20s} {note[:80]}")

    out = os.path.join(os.path.dirname(os.path.abspath(__file__)), "category_probe.json")
    with open(out, "w") as fh:
        json.dump([{"category": c, "spec": s, "note": n,
                    "messages": [{"method": m["m"],
                                  "text": m.get("text") or m.get("caption") or m.get("file"),
                                  "parse_mode": m.get("parse_mode")} for m in calls]}
                   for c, s, calls, n in rows], fh, ensure_ascii=False, indent=2)
    print("\nfull transcript:", out)
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception:
        traceback.print_exc()
        raise SystemExit(2)
