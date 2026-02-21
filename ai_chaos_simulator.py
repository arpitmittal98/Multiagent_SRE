#!/usr/bin/env python3
"""
SRE AI Agent — Generative Chaos Simulator
═════════════════════════════════════════
Dynamically generates highly realistic telemetry and logs using AWS Bedrock
based on an English prompt, and pushes them to Datadog for the demo.

Usage:
    python ai_chaos_simulator.py --service CheckoutAPI --scenario "Postgres deadlock"

Requires: AWS credentials, DD_API_KEY, DD_APP_KEY in .env
"""

from __future__ import annotations

import argparse
import random
import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx
from dotenv import load_dotenv

from config import get_settings
from tools.bedrock_llm import generate_synthetic_logs

load_dotenv()

HOSTS = ["ip-10-0-1-42.ec2.internal", "ip-10-0-2-87.ec2.internal", "ip-10-0-3-15.ec2.internal"]

def submit_metrics(
    settings: Any,
    service: str,
    error_code: str = "500",
) -> None:
    """Submit realistic metric spike pattern."""
    now = datetime.now(timezone.utc)
    series_points = []

    for minutes_ago in range(60, 0, -1):
        ts = int((now - timedelta(minutes=minutes_ago)).timestamp())

        if minutes_ago > 30:
            errors, requests, latency = random.uniform(0.0, 2.0), random.uniform(800, 1200), random.uniform(35, 55)
        elif minutes_ago > 15:
            progress = (30 - minutes_ago) / 15
            errors = random.uniform(5, 15) + (progress * 35)
            requests = random.uniform(1500, 2500)
            latency = random.uniform(200, 2000) + (progress * 8000)
        elif minutes_ago > 5:
            errors, requests, latency = random.uniform(35, 55), random.uniform(2000, 3000), random.uniform(8000, 15000)
        else:
            progress = (5 - minutes_ago) / 5
            errors = random.uniform(2, 8) * (1 - progress * 0.7)
            requests = random.uniform(1000, 1500)
            latency = random.uniform(40, 200)

        series_points.append({
            "timestamp": ts,
            "errors": round(errors, 2),
            "requests": round(requests, 0),
            "latency_p99": round(latency, 1),
        })

    headers = {"DD-API-KEY": settings.dd_api_key, "Content-Type": "application/json"}
    base_url = f"https://api.{settings.dd_site}"

    metrics = [
        ("trace.http.request.errors", "errors", "count"),
        ("trace.http.request.hits", "requests", "count"),
        ("trace.http.request.duration.by.service.99p", "latency_p99", "gauge"),
    ]

    with httpx.Client(timeout=30) as client:
        for metric_name, field, metric_type in metrics:
            payload = {
                "series": [
                    {
                        "metric": metric_name,
                        "type": metric_type,
                        "points": [[p["timestamp"], p[field]] for p in series_points],
                        "tags": [f"service:{service}", f"env:{settings.dd_env}", f"http.status_code:{error_code}", "source:ai_chaos"],
                        "host": random.choice(HOSTS),
                    }
                ]
            }
            resp = client.post(f"{base_url}/api/v1/series", headers=headers, json=payload)
            if resp.status_code == 202:
                print(f"  [OK] {metric_name}: {len(series_points)} points generated")
            else:
                print(f"  [FAIL] {metric_name}: {resp.status_code} -- {resp.text[:100]}")


def submit_ai_logs(
    settings: Any,
    service: str,
    scenario: str,
) -> None:
    print("  => Calling AWS Bedrock Claude 3.5 Sonnet to hallucinate logs...")
    generated_logs = generate_synthetic_logs(scenario, service, log_count=30)
    
    if not generated_logs:
        print("  [FAIL] Bedrock failed to generate JSON logs. Try again.")
        return

    print(f"  => Bedrock successfully generated {len(generated_logs)} unique log structures.")
    
    now = datetime.now(timezone.utc)
    headers = {"DD-API-KEY": settings.dd_api_key, "Content-Type": "application/json"}
    base_url = f"https://http-intake.logs.{settings.dd_site}"

    payloads = []
    
    for i, ai_log in enumerate(generated_logs):
        if i < 3:
            mins = random.uniform(55, 35)
        elif i < len(generated_logs) - 3:
            mins = random.uniform(28, 6)
        else:
            mins = random.uniform(5, 1)

        ts = (now - timedelta(minutes=mins)).isoformat()
        req_id = f"req-{random.randint(100000, 999999)}"
        http_code = ai_log.get("http_status", "500")

        log_entry = {
            "ddsource": "python",
            "ddtags": f"service:{service},env:{settings.dd_env},source:ai_chaos,http.status_code:{http_code}",
            "hostname": random.choice(HOSTS),
            "service": service,
            "status": ai_log.get("status", "error"),
            "message": f"[ERROR] {ts} {req_id} -- {ai_log.get('message', 'Unknown Error')}",
            "attributes": {
                "http": {
                    "url": f"https://{service.lower()}.prod.internal{ai_log.get('path', '/api')}",
                    "status_code": str(http_code),
                    "request_id": req_id,
                },
                "error": {
                    "kind": ai_log.get("kind", "UnknownError"),
                },
            },
        }
        payloads.append(log_entry)

    with httpx.Client(timeout=30) as client:
        # Submit all at once since it's < 1000
        resp = client.post(f"{base_url}/api/v2/logs", headers=headers, json=payloads)
        if resp.status_code == 202:
            print(f"  [OK] Successfully pushed {len(payloads)} AI-generated logs to Datadog.")
        else:
            print(f"  [FAIL] Log push failed: {resp.status_code} -- {resp.text[:100]}")


def main():
    parser = argparse.ArgumentParser(description="Generative AI Chaos Simulator powered by Bedrock")
    parser.add_argument("--service", required=True, help="Service name")
    parser.add_argument("--scenario", required=True, help="Describe the incident (e.g. 'AWS RDS max connections exceeded')")
    args = parser.parse_args()

    settings = get_settings()

    print("\n+======================================================+")
    print("|      ** AWS BEDROCK GENERATIVE CHAOS SIMULATOR **    |")
    print("+======================================================+")
    print(f"|  Service:  {args.service}")
    print(f"|  Scenario: {args.scenario}")
    print("+======================================================+\n")

    print("[METRICS] Generating metric anomaly profile...")
    submit_metrics(settings, args.service)
    
    print("\n[LOGS] Generating synthetic traces via LLM...")
    submit_ai_logs(settings, args.service, args.scenario)

    print("\n======================================================")
    print("Done! Wait ~1-2 min for Datadog indexing, then investigate.")

if __name__ == "__main__":
    main()
