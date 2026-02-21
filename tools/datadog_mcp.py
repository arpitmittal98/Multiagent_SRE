"""
SRE AI Agent — Datadog MCP Integration
───────────────────────────────────────
Queries Datadog metrics and logs via the REST API,
structured as an MCP-style tool layer the LangGraph
agent can invoke during the *investigate* step.

All public functions are decorated with ``@LLMObs.workflow()``
so every call is captured as a traced span inside the
Datadog LLM Observability dashboard.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from ddtrace.llmobs.decorators import workflow

from config import get_settings

logger = logging.getLogger(__name__)

# ── Helpers ──────────────────────────────────────────────────────

_DATADOG_HEADERS: dict[str, str] | None = None


def _headers() -> dict[str, str]:
    """Lazily build auth headers from settings."""
    global _DATADOG_HEADERS
    if _DATADOG_HEADERS is None:
        cfg = get_settings()
        _DATADOG_HEADERS = {
            "DD-API-KEY": cfg.dd_api_key,
            "DD-APPLICATION-KEY": cfg.dd_app_key,
            "Content-Type": "application/json",
        }
    return _DATADOG_HEADERS


def _base_url() -> str:
    cfg = get_settings()
    return f"https://api.{cfg.dd_site}"


# ── Public API ───────────────────────────────────────────────────


@workflow(name="datadog.query_metrics")
async def query_metrics(
    service_name: str,
    metric: str = "trace.http.request.errors",
    period_minutes: int = 60,
) -> list[dict[str, Any]]:
    """
    Query a Datadog time-series metric for *service_name*
    over the last *period_minutes*.

    Returns a list of ``{"timestamp": ..., "value": ...}`` points.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - (period_minutes * 60)

    query = f"avg:{metric}{{service:{service_name.lower()}}}.as_count()"

    logger.info("Datadog metric query: %s  [%s → %s]", query, start, now)

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.get(
                f"{_base_url()}/api/v1/query",
                headers=_headers(),
                params={"from": start, "to": now, "query": query},
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Datadog metrics API error %s: %s", exc.response.status_code, exc.response.text[:200])
            return []
        except Exception as exc:
            logger.error("Datadog metrics request failed: %s", exc)
            return []

    series = data.get("series", [])
    if not series:
        logger.warning("No metric series returned for %s", query)
        return []

    points = [
        {"timestamp": int(pt[0]), "value": pt[1]}
        for pt in series[0].get("pointlist", [])
    ]
    logger.info("Received %d data points for %s", len(points), service_name)
    return points


@workflow(name="datadog.search_logs")
async def search_logs(
    service_name: str,
    error_type: str = "500",
    period_minutes: int = 60,
    limit: int = 50,
) -> list[dict[str, Any]]:
    """
    Search Datadog logs for recent errors matching *service_name*
    and *error_type*.

    Returns up to *limit* log entries with timestamp, message,
    status, and attributes.
    """
    now = datetime.now(timezone.utc)
    start = now - timedelta(minutes=period_minutes)

    payload = {
        "filter": {
            "query": f"service:{service_name.lower()} status:error @http.status_code:{error_type}",
            "from": start.isoformat(),
            "to": now.isoformat(),
        },
        "sort": "timestamp",
        "page": {"limit": limit},
    }

    logger.info("Datadog log search: %s", json.dumps(payload["filter"]["query"]))

    async with httpx.AsyncClient(timeout=30) as client:
        try:
            resp = await client.post(
                f"{_base_url()}/api/v2/logs/events/search",
                headers=_headers(),
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()
        except httpx.HTTPStatusError as exc:
            logger.error("Datadog logs API error %s: %s", exc.response.status_code, exc.response.text[:200])
            return []
        except Exception as exc:
            logger.error("Datadog logs request failed: %s", exc)
            return []

    logs = []
    for entry in data.get("data", []):
        attrs = entry.get("attributes", {})
        logs.append(
            {
                "timestamp": attrs.get("timestamp", ""),
                "message": attrs.get("message", ""),
                "status": attrs.get("status", ""),
                "host": attrs.get("host", ""),
                "attributes": attrs.get("attributes", {}),
            }
        )

    logger.info("Retrieved %d log entries for %s", len(logs), service_name)
    return logs


@workflow(name="datadog.get_service_health")
async def get_service_health(service_name: str) -> dict[str, Any]:
    """
    Return a high-level health snapshot for *service_name*:
    error rate, request count, and p99 latency over the last hour.
    """
    now = int(datetime.now(timezone.utc).timestamp())
    start = now - 3600  # last hour

    queries = {
        "error_rate": f"avg:trace.http.request.errors{{service:{service_name.lower()}}}.as_rate()",
        "request_count": f"sum:trace.http.request.hits{{service:{service_name.lower()}}}.as_count()",
        "p99_latency_ms": f"avg:trace.http.request.duration.by.service.99p{{service:{service_name.lower()}}}",
    }

    health: dict[str, Any] = {"service": service_name, "period": "last_1h"}

    async with httpx.AsyncClient(timeout=30) as client:
        for key, q in queries.items():
            try:
                resp = await client.get(
                    f"{_base_url()}/api/v1/query",
                    headers=_headers(),
                    params={"from": start, "to": now, "query": q},
                )
                resp.raise_for_status()
                series = resp.json().get("series", [])
                if series:
                    points = series[0].get("pointlist", [])
                    values = [p[1] for p in points if p[1] is not None]
                    health[key] = round(sum(values) / len(values), 4) if values else 0
                else:
                    health[key] = 0
            except Exception as exc:
                logger.error("Failed to fetch %s: %s", key, exc)
                health[key] = None

    logger.info("Service health for %s: %s", service_name, health)
    return health
