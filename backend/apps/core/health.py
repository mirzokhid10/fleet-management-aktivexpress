"""Checks that the services the app depends on answer."""

from __future__ import annotations

from django.core.cache import cache
from django.db import connection


def check_database() -> dict:
    with connection.cursor() as cur:
        cur.execute("SELECT postgis_lib_version()")
        return {"ok": True, "postgis": cur.fetchone()[0]}


def check_cache() -> dict:
    cache.set("health:ping", "pong", 10)
    return {"ok": cache.get("health:ping") == "pong"}


CHECKS = {"database": check_database, "cache": check_cache}


def run_checks(checks: dict = CHECKS) -> dict:
    results = {}
    for name, check in checks.items():
        try:
            results[name] = check()
        except Exception as exc:  # report, never crash the health endpoint
            results[name] = {"ok": False, "error": exc.__class__.__name__}
    return {"ok": all(r["ok"] for r in results.values()), "checks": results}
