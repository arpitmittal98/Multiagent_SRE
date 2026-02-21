#!/usr/bin/env python3
"""
SRE AI Agent — Chaos Simulator
═══════════════════════════════
Pushes realistic synthetic telemetry into Datadog so the
SRE agent has real data to investigate during a live demo.

Timeline simulated (all within the last ~60 minutes):
  [T-60m → T-30m]  Normal baseline traffic
  [T-30m → T-15m]  Error spike begins (connection pool exhaustion)
  [T-15m → T-5m]   Peak error storm
  [T-5m  → now]    Partial recovery (like the agent just fixed it)

Usage:
    python chaos_simulator.py                   # uses .env for credentials
    python chaos_simulator.py --service PaymentGateway --error 502

Requires: DD_API_KEY, DD_APP_KEY in .env (or environment).
"""

from __future__ import annotations

import argparse
import json
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

from config import get_settings

# ── Load env ─────────────────────────────────────────────────────
load_dotenv()


# ── Constants ────────────────────────────────────────────────────

ERROR_MESSAGES = [
    "redis.exceptions.ConnectionError: Error 111 connecting to auth-cache-prod.abc123.use1.cache.amazonaws.com:6379. Connection refused.",
    "redis.exceptions.ConnectionError: max number of clients reached",
    "redis.exceptions.TimeoutError: Timeout reading from auth-cache-prod.abc123.use1.cache.amazonaws.com:6379",
    "ConnectionPool.get_connection: pool exhausted (max_connections=50, current=50)",
    "sqlalchemy.exc.OperationalError: (psycopg2.pool.PoolError) connection pool exhausted",
    "botocore.exceptions.ClientError: An error occurred (ThrottlingException) when calling the GetItem operation: Rate exceeded",
    "urllib3.exceptions.MaxRetryError: HTTPSConnectionPool(host='internal-api.prod', port=443): Max retries exceeded",
    "socket.timeout: timed out after 30.0 seconds waiting for response from upstream",
    "aiohttp.client_exceptions.ServerDisconnectedError: Server disconnected",
    "grpc._channel._InactiveRpcError: <_InactiveRpcError of RPC that terminated with: status = StatusCode.UNAVAILABLE, details = 'Connection reset by peer'>",
]

STACK_TRACES = [
    'File "/app/services/auth.py", line 142, in authenticate_user\n    session = await redis_pool.get_connection()\n  File "/app/cache/pool.py", line 87, in get_connection\n    raise ConnectionPoolExhausted(f"Pool exhausted: {self.active}/{self.max_size}")',
    'File "/app/api/v2/auth/token.py", line 56, in create_token\n    cached = await cache.get(f"user:{user_id}:session")\n  File "/app/cache/redis_client.py", line 34, in get\n    conn = self.pool.get_connection("GET")\n  File "/usr/local/lib/python3.11/site-packages/redis/connection.py", line 1387, in get_connection\n    raise ConnectionError("max number of clients reached")',
    'File "/app/middleware/rate_limit.py", line 23, in __call__\n    count = await self.redis.incr(key)\n  File "/app/cache/redis_client.py", line 52, in incr\n    return await asyncio.wait_for(self._execute("INCR", key), timeout=5.0)\nasyncio.exceptions.TimeoutError',
]

HOSTS = ["ip-10-0-1-42.ec2.internal", "ip-10-0-2-87.ec2.internal", "ip-10-0-3-15.ec2.internal"]

REQUEST_PATHS = [
    "/api/v2/auth/token",
    "/api/v2/auth/refresh",
    "/api/v2/auth/validate",
    "/api/v2/auth/logout",
    "/api/v2/auth/session",
]


# ── Metric Submission ────────────────────────────────────────────


def submit_metrics(
    settings: Any,
    service: str,
    error_code: str,
) -> None:
    """
    Submit a realistic time-series of error-rate metrics to Datadog.

    Creates the pattern:
        baseline → spike → peak → partial recovery
    """
    now = datetime.now(timezone.utc)
    series_points = []

    for minutes_ago in range(60, 0, -1):
        ts = int((now - timedelta(minutes=minutes_ago)).timestamp())

        if minutes_ago > 30:
            # Baseline: low error rate
            errors = random.uniform(0.0, 2.0)
            requests = random.uniform(800, 1200)
            latency_p99 = random.uniform(35, 55)
        elif minutes_ago > 15:
            # Spike building
            progress = (30 - minutes_ago) / 15  # 0 → 1
            errors = random.uniform(5, 15) + (progress * 35)
            requests = random.uniform(1500, 2500)
            latency_p99 = random.uniform(200, 2000) + (progress * 8000)
        elif minutes_ago > 5:
            # Peak error storm
            errors = random.uniform(35, 55)
            requests = random.uniform(2000, 3000)
            latency_p99 = random.uniform(8000, 15000)
        else:
            # Recovery (agent just fixed it)
            progress = (5 - minutes_ago) / 5  # 1 → 0 recovery
            errors = random.uniform(2, 8) * (1 - progress * 0.7)
            requests = random.uniform(1000, 1500)
            latency_p99 = random.uniform(40, 200)

        series_points.append({
            "timestamp": ts,
            "errors": round(errors, 2),
            "requests": round(requests, 0),
            "latency_p99": round(latency_p99, 1),
        })

    # Submit each metric series
    headers = {
        "DD-API-KEY": settings.dd_api_key,
        "Content-Type": "application/json",
    }
    base_url = f"https://api.{settings.dd_site}"

    metric_defs = [
        ("trace.http.request.errors", "errors", "count"),
        ("trace.http.request.hits", "requests", "count"),
        ("trace.http.request.duration.by.service.99p", "latency_p99", "gauge"),
    ]

    with httpx.Client(timeout=30) as client:
        for metric_name, field, metric_type in metric_defs:
            payload = {
                "series": [
                    {
                        "metric": metric_name,
                        "type": metric_type,
                        "points": [[p["timestamp"], p[field]] for p in series_points],
                        "tags": [
                            f"service:{service}",
                            f"env:{settings.dd_env}",
                            f"http.status_code:{error_code}",
                            "source:chaos_simulator",
                        ],
                        "host": random.choice(HOSTS),
                    }
                ]
            }

            resp = client.post(
                f"{base_url}/api/v1/series",
                headers=headers,
                json=payload,
            )

            if resp.status_code == 202:
                print(f"  [OK] {metric_name}: {len(series_points)} points submitted")
            else:
                print(f"  [FAIL] {metric_name}: {resp.status_code} -- {resp.text[:200]}")


# ── Log Submission ───────────────────────────────────────────────


def submit_logs(
    settings: Any,
    service: str,
    error_code: str,
    log_count: int = 47,
) -> None:
    """
    Submit realistic error log entries to Datadog.

    Concentrates logs in the T-30m → T-5m window (the error storm).
    """
    now = datetime.now(timezone.utc)
    headers = {
        "DD-API-KEY": settings.dd_api_key,
        "Content-Type": "application/json",
    }
    base_url = f"https://http-intake.logs.{settings.dd_site}"

    logs = []

    for i in range(log_count):
        # Most logs in the 30-5 minute-ago window
        if i < 3:
            minutes_ago = random.uniform(55, 35)  # a few early warnings
        elif i < log_count - 5:
            minutes_ago = random.uniform(28, 6)    # bulk during storm
        else:
            minutes_ago = random.uniform(5, 1)     # tail during recovery

        timestamp = (now - timedelta(minutes=minutes_ago)).isoformat()
        host = random.choice(HOSTS)
        path = random.choice(REQUEST_PATHS)
        error_msg = random.choice(ERROR_MESSAGES)
        trace_snippet = random.choice(STACK_TRACES)
        request_id = f"req-{random.randint(100000, 999999)}"
        user_id = f"user-{random.randint(10000, 99999)}"

        log_entry = {
            "ddsource": "python",
            "ddtags": f"service:{service},env:{settings.dd_env},source:chaos_simulator,http.status_code:{error_code}",
            "hostname": host,
            "service": service,
            "status": "error",
            "message": (
                f"[ERROR] {timestamp} {request_id} "
                f"HTTP {error_code} on {path} -- {error_msg}"
            ),
            "attributes": {
                "http": {
                    "method": "POST",
                    "url": f"https://{service.lower()}.prod.internal{path}",
                    "status_code": int(error_code),
                    "request_id": request_id,
                },
                "usr": {"id": user_id},
                "error": {
                    "kind": error_msg.split(":")[0].strip(),
                    "message": error_msg,
                    "stack": trace_snippet,
                },
                "network": {
                    "client": {"ip": f"10.0.{random.randint(1,3)}.{random.randint(10,250)}"},
                },
                "custom": {
                    "redis_pool_active": random.randint(45, 50) if "pool" in error_msg.lower() else random.randint(10, 30),
                    "redis_pool_max": 50,
                    "response_time_ms": random.randint(5000, 30000),
                },
            },
        }
        logs.append(log_entry)

    # Datadog accepts up to 1000 logs per request
    batch_size = 50
    total_sent = 0

    with httpx.Client(timeout=30) as client:
        for batch_start in range(0, len(logs), batch_size):
            batch = logs[batch_start:batch_start + batch_size]
            resp = client.post(
                f"{base_url}/api/v2/logs",
                headers=headers,
                json=batch,
            )
            if resp.status_code == 202:
                total_sent += len(batch)
            else:
                print(f"  [FAIL] Log batch failed: {resp.status_code} -- {resp.text[:200]}")

    print(f"  [OK] {total_sent} error logs submitted")


# ── Main ─────────────────────────────────────────────────────────


def main():
    parser = argparse.ArgumentParser(
        description="Push chaos telemetry to Datadog for a live SRE agent demo."
    )
    parser.add_argument(
        "--service", default="UserAuth",
        help="Service name to simulate errors for (default: UserAuth)"
    )
    parser.add_argument(
        "--error", default="500",
        help="HTTP error code (default: 500)"
    )
    parser.add_argument(
        "--logs", type=int, default=47,
        help="Number of error log entries to submit (default: 47)"
    )
    args = parser.parse_args()

    settings = get_settings()

    print()
    print("+==================================================+")
    print("|         ** SRE CHAOS SIMULATOR **                 |")
    print("+==================================================+")
    print(f"|  Service:    {args.service:<36} |")
    print(f"|  Error Code: {args.error:<36} |")
    print(f"|  Log Count:  {args.logs:<36} |")
    print(f"|  DD Site:    {settings.dd_site:<36} |")
    print("+==================================================+")
    print()

    # Phase 1: Metrics
    print("[METRICS] Phase 1 -- Submitting metrics (60 data points x 3 series)...")
    try:
        submit_metrics(settings, args.service, args.error)
    except Exception as e:
        print(f"  [FAIL] Metrics failed: {e}")
        print("  [TIP] Check your DD_API_KEY in .env")
        sys.exit(1)

    print()

    # Phase 2: Logs
    print(f"[LOGS] Phase 2 -- Submitting {args.logs} error logs...")
    try:
        submit_logs(settings, args.service, args.error, args.logs)
    except Exception as e:
        print(f"  [FAIL] Logs failed: {e}")
        print("  [TIP] Check your DD_API_KEY in .env")
        sys.exit(1)

    print()
    print("=" * 52)
    print("[DONE] Chaos simulation complete!")
    print()
    print("Next steps:")
    print(f"   1. Wait ~2 minutes for Datadog to index the data")
    print(f"   2. Check Datadog -> Logs -> search: service:{args.service}")
    print(f"   3. Run the SRE agent: python server.py")
    print(f"   4. POST to /api/investigate with:")
    print(f'      {{"service_name": "{args.service}", "error_type": "{args.error}"}}')
    print()


if __name__ == "__main__":
    main()
