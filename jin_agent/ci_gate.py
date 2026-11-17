"""P26 - offline CI gate: compile/import + unit tests + evaluator quick check.

``python -m jin_agent ci-gate`` aik compact JSON verdict print karta hai aur
exit code **0 sirf tab** deta hai jab saare checks pass hon. Sab kuch offline:
koi network call nahi, koi pip install nahi, koi server/bot start nahi hota.
"""

from __future__ import annotations

import importlib
import io
import os
import py_compile
import shutil
import tempfile
import time
import unittest
from pathlib import Path

from . import VERSION, evaluator, orchestrator, store, util

PKG = Path(__file__).resolve().parent


def package_modules() -> list[str]:
    """Package ke top-level module names (``__init__`` / ``__main__`` chhod kar)."""
    return sorted(p.stem for p in PKG.glob("*.py") if not p.stem.startswith("__"))


def compile_file(path) -> tuple[bool, str]:
    """Aik .py file ko throwaway ``.pyc`` par compile karo; error string wapas."""
    target = Path(path)
    try:
        with tempfile.TemporaryDirectory(prefix="jin-compile-") as tmp:
            py_compile.compile(str(target), cfile=str(Path(tmp) / (target.stem + ".pyc")),
                               doraise=True)
        return True, ""
    except py_compile.PyCompileError as exc:
        return False, util.truncate(str(exc), 200)
    except OSError as exc:
        return False, f"{type(exc).__name__}: {util.truncate(str(exc), 160)}"


def check_imports() -> dict:
    """(a) Har package module compile + import - syntax/import break yahin pakra jata hai."""
    started = time.monotonic()
    names = package_modules()
    errors: list[str] = []
    imported = 0
    for name in names:
        ok, error = compile_file(PKG / f"{name}.py")
        if not ok:
            errors.append(f"{name}.py: {error}")
            continue
        try:
            importlib.import_module(f"jin_agent.{name}")
            imported += 1
        except Exception as exc:  # import-time crash bhi gate fail hai
            errors.append(f"{name}.py: import {type(exc).__name__}: {util.truncate(str(exc), 120)}")
    return {"ok": not errors, "modules": len(names), "imported": imported,
            "errors": errors, "duration_ms": round((time.monotonic() - started) * 1000)}


def check_unit_tests(pattern: str = "test_*.py", verbosity: int = 0) -> dict:
    """(b) Poora offline unittest suite (in-process, koi subprocess nahi)."""
    started = time.monotonic()
    loader = unittest.TestLoader()
    try:
        suite = loader.discover(str(PKG / "tests"), pattern=pattern)
    except Exception as exc:
        return {"ok": False, "tests": 0, "failures": 0, "errors": 1,
                "detail": f"{type(exc).__name__}: {util.truncate(str(exc), 160)}",
                "duration_ms": round((time.monotonic() - started) * 1000)}
    stream = io.StringIO()
    result = unittest.TextTestRunner(stream=stream, verbosity=verbosity).run(suite)
    broken = [str(t).split(" ")[0] for t, _ in (result.failures + result.errors)]
    return {"ok": result.wasSuccessful(), "tests": result.testsRun,
            "failures": len(result.failures), "errors": len(result.errors),
            "skipped": len(result.skipped), "failing": broken[:10],
            "duration_ms": round((time.monotonic() - started) * 1000)}


def check_evaluator_quick(queries: int = 3) -> dict:
    """(c) Evaluator ka offline quick check - throwaway DB, zero network."""
    started = time.monotonic()
    count = max(1, min(int(queries or 1), len(evaluator.QUERIES)))
    specs = evaluator.QUERIES[:count]
    original = os.environ.get("JIN_AGENT_DATA")
    tmp = tempfile.mkdtemp(prefix="jin-ci-gate-")
    os.environ["JIN_AGENT_DATA"] = tmp
    crashes, fabricated, items, provenances = 0, 0, 0, []
    try:
        store.init_db()
        for spec in specs:
            try:
                out = orchestrator.run(spec["q"], live=False, limit=5, save=False)
            except Exception:
                crashes += 1
                continue
            fabricated += int(out["audit"]["fabricated"])
            provenances.append(float(out["audit"]["provenance_pct"]))
            items += len(out["items"])
    finally:
        if original is None:
            os.environ.pop("JIN_AGENT_DATA", None)
        else:
            os.environ["JIN_AGENT_DATA"] = original
        shutil.rmtree(tmp, ignore_errors=True)
    provenance = round(sum(provenances) / len(provenances), 1) if provenances else 0.0
    ok = crashes == 0 and fabricated == 0 and provenance >= 100.0 and items > 0
    return {"ok": ok, "mode": "offline-fixture", "queries": len(specs),
            "crashes": crashes, "fabricated": fabricated,
            "provenance_pct": provenance, "items": items,
            "duration_ms": round((time.monotonic() - started) * 1000)}


def run(include_unittests: bool = True, queries: int = 3) -> dict:
    """Poora gate chalao. ``ok`` sirf tab True jab har check pass ho."""
    started = time.monotonic()
    checks = {"imports": check_imports()}
    if include_unittests:
        checks["unit_tests"] = check_unit_tests()
    checks["evaluator"] = check_evaluator_quick(queries)
    ok = all(bool(check.get("ok")) for check in checks.values())
    return {"ok": ok, "version": VERSION, "date_checked": util.now_iso(),
            "checks": checks, "duration_ms": round((time.monotonic() - started) * 1000)}
