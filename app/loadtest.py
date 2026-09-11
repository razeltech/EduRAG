"""LAN smoke load test against a running EduRAG server (stdlib only)."""
from __future__ import annotations

import statistics
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any


def _one(url: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(url, timeout=timeout) as resp:
            body = resp.read(2048)
            ms = (time.perf_counter() - started) * 1000
            return {"ok": 200 <= resp.status < 400, "ms": ms, "bytes": len(body), "error": None}
    except urllib.error.HTTPError as exc:
        ms = (time.perf_counter() - started) * 1000
        return {"ok": False, "ms": ms, "bytes": 0, "error": f"HTTP {exc.code}"}
    except Exception as exc:
        ms = (time.perf_counter() - started) * 1000
        return {"ok": False, "ms": ms, "bytes": 0, "error": str(exc)}


def run_load_test(
    *,
    host: str = "127.0.0.1",
    port: int = 4747,
    clients: int = 32,
    per_client: int = 8,
    timeout: float = 8.0,
    path: str = "/v1/health",
) -> dict[str, Any]:
    url = f"http://{host}:{port}{path}"
    total = max(1, clients) * max(1, per_client)
    workers = max(1, min(clients, 100))
    probe = _one(url, timeout)
    if not probe["ok"] and probe["error"]:
        return {
            "ok": False,
            "url": url,
            "error": probe["error"],
            "hint": "Start the server first: python -m app serve --host 0.0.0.0 --port 4747",
        }

    started = time.perf_counter()
    rows: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = [pool.submit(_one, url, timeout) for _ in range(total)]
        for fut in as_completed(futs):
            rows.append(fut.result())
    elapsed = time.perf_counter() - started
    lat = sorted(r["ms"] for r in rows)
    ok_n = sum(1 for r in rows if r["ok"])
    errs = [r["error"] for r in rows if r["error"]]
    def pct(p: float) -> float:
        if not lat:
            return 0.0
        idx = min(len(lat) - 1, max(0, int(round((p / 100) * (len(lat) - 1)))))
        return round(lat[idx], 1)

    return {
        "ok": ok_n == len(rows),
        "url": url,
        "clients": workers,
        "requests": len(rows),
        "ok_count": ok_n,
        "errors": len(rows) - ok_n,
        "seconds": round(elapsed, 2),
        "rps": round(len(rows) / max(elapsed, 0.001), 1),
        "latency_ms": {
            "min": round(lat[0], 1) if lat else 0,
            "p50": pct(50),
            "p95": pct(95),
            "p99": pct(99),
            "max": round(lat[-1], 1) if lat else 0,
            "mean": round(statistics.mean(lat), 1) if lat else 0,
        },
        "sample_errors": list(dict.fromkeys(errs))[:5],
    }


def format_report(result: dict[str, Any]) -> str:
    if result.get("error") and "requests" not in result:
        return (
            "LOAD TEST\n=========\n"
            f"  Could not reach {result.get('url')}\n"
            f"  {result.get('error')}\n"
            f"  {result.get('hint')}"
        )
    lat = result.get("latency_ms") or {}
    lines = [
        "LOAD TEST",
        "=========",
        f"  {result.get('url')}",
        f"  clients={result.get('clients')}  requests={result.get('requests')}  "
        f"ok={result.get('ok_count')}  errors={result.get('errors')}",
        f"  {result.get('seconds')}s  {result.get('rps')} req/s",
        f"  latency ms  min={lat.get('min')}  p50={lat.get('p50')}  "
        f"p95={lat.get('p95')}  p99={lat.get('p99')}  max={lat.get('max')}",
    ]
    samples = result.get("sample_errors") or []
    if samples:
        lines.append("  errors: " + "; ".join(samples))
    lines.append("  Target: 30-100 concurrent LAN clients on health/personas is a smoke test.")
    lines.append("  Chat+RAG under that load needs GPU headroom; watch VRAM while chatting.")
    return "\n".join(lines)
