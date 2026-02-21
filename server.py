"""
AI War Room -- FastAPI Server with SSE Streaming
-------------------------------------------------
Provides a REST + SSE API for the multi-agent war room.
React frontend consumes SSE events showing each agent's
debate messages in real-time.

Initializes Datadog LLM Observability on startup.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

# Disable ddtrace APM (avoids errors connecting to localhost:8126).
# Only LLM Observability (agentless) is used.
os.environ.setdefault("DD_TRACE_ENABLED", "false")

from ddtrace.llmobs import LLMObs
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from agent import run_war_room
from tools.strands_remediation import simulate_remediation
from config import get_settings

logger = logging.getLogger(__name__)


# -- Lifespan ---------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan: export AWS creds, enable Datadog LLM
    Observability on startup, flush on shutdown.
    """
    cfg = get_settings()

    # -- Export AWS creds as OS env vars --
    if cfg.aws_access_key_id:
        os.environ["AWS_ACCESS_KEY_ID"] = cfg.aws_access_key_id
        os.environ["AWS_SECRET_ACCESS_KEY"] = cfg.aws_secret_access_key
        os.environ["AWS_DEFAULT_REGION"] = cfg.aws_region
        if cfg.aws_session_token:
            os.environ["AWS_SESSION_TOKEN"] = cfg.aws_session_token
        logger.info("AWS credentials exported to environment")

    # -- Enable Datadog LLM Observability --
    LLMObs.enable(
        ml_app="ai-war-room",
        api_key=cfg.dd_api_key,
        site=cfg.dd_site,
        env=cfg.dd_env,
        service=cfg.dd_service,
        agentless_enabled=True,
    )
    logger.info(
        "[OK] Datadog LLM Observability enabled  (service=%s, env=%s)",
        cfg.dd_service, cfg.dd_env,
    )

    yield

    LLMObs.flush()
    logger.info("Datadog LLM Observability flushed and shut down.")


# -- App ---------------------------------------------------------------


app = FastAPI(
    title="AI War Room",
    description="Multi-agent incident debate system with Datadog + Bedrock",
    version="2.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# -- Request / Response Models ----------------------------------------


class WarRoomRequest(BaseModel):
    """Payload to activate the war room."""
    service_name: str
    error_type: str = "500"


class RemediateRequest(BaseModel):
    """Payload to trigger actionable agent remediation."""
    service_name: str
    incident_summary: str


class WarRoomResponse(BaseModel):
    """Returned after the full war room completes (non-streaming)."""
    service_name: str
    error_type: str
    consensus: str
    war_room_summary: str
    debate_message_count: int
    total_message_count: int


# -- Endpoints ---------------------------------------------------------


@app.post("/api/investigate", response_model=WarRoomResponse)
async def investigate(req: WarRoomRequest):
    """
    Run the full war room pipeline synchronously and return the result.
    """
    try:
        state = await run_war_room(req.service_name, req.error_type)
        return WarRoomResponse(
            service_name=state.get("service_name", ""),
            error_type=state.get("error_type", ""),
            consensus=state.get("consensus", ""),
            war_room_summary=state.get("war_room_summary", ""),
            debate_message_count=len(state.get("debate_log", [])),
            total_message_count=len(state.get("messages", [])),
        )
    except Exception as exc:
        logger.exception("War room failed")
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@app.post("/api/investigate/stream")
async def investigate_stream(req: WarRoomRequest):
    """
    SSE endpoint. Streams each agent message as it is emitted,
    then sends the consensus and a final [DONE] event.
    """

    async def event_generator() -> AsyncGenerator[dict, None]:
        """Run the war room and yield SSE events."""
        q = asyncio.Queue()

        task = asyncio.create_task(run_war_room(req.service_name, req.error_type, q))

        while not task.done():
            try:
                item = await asyncio.wait_for(q.get(), timeout=0.1)
                if isinstance(item.get("data"), dict):
                    item["data"] = json.dumps(item["data"])
                yield item
            except asyncio.TimeoutError:
                continue

        # Task done, flush queue
        while not q.empty():
            item = await q.get()
            if isinstance(item.get("data"), dict):
                item["data"] = json.dumps(item["data"])
            yield item

        final_state = task.result()

        # Send consensus as separate event
        yield {
            "event": "consensus",
            "data": json.dumps({
                "consensus": final_state.get("consensus", ""),
            }),
        }

        # Send war room summary as final report
        yield {
            "event": "report",
            "data": json.dumps({
                "war_room_summary": final_state.get("war_room_summary", ""),
            }),
        }

        yield {"event": "done", "data": "[DONE]"}

    return EventSourceResponse(event_generator())


@app.post("/api/remediate/stream")
async def remediate_stream(req: RemediateRequest):
    """
    SSE endpoint. Streams mocked terminal execution lines for remediation.
    """
    async def event_generator() -> AsyncGenerator[dict, None]:
        async for log_line in simulate_remediation(req.service_name, req.incident_summary):
            if log_line == "[DONE]":
                yield {"event": "done", "data": "[DONE]"}
            else:
                yield {"event": "log", "data": json.dumps({"text": log_line})}
    
    return EventSourceResponse(event_generator())


@app.get("/health")
async def health():
    """Liveness / readiness probe."""
    return {"status": "ok", "service": "ai-war-room"}


@app.get("/api/llm/metrics")
async def llm_metrics():
    """
    Simulated endpoint for Datadog LLM Observability telemetry.
    In a real app, this queries /api/v2/logs/events/search for @type:span @llm.usage
    """
    import time
    # Creates a stable but slowly growing number based on current hour
    growth = int(time.time() / 3600) % 500
    
    base_reqs = 1240
    base_prompt = 1680500
    base_completion = 310200
    
    p_tokens = base_prompt + (growth * 1250)
    c_tokens = base_completion + (growth * 400)
    
    # Claude 3.5 Sonnet pricing: $3.00 / 1M prompt, $15.00 / 1M completion
    cost = (p_tokens / 1_000_000 * 3.00) + (c_tokens / 1_000_000 * 15.00)
    
    return {
        "total_requests": base_reqs + growth,
        "prompt_tokens": p_tokens,
        "completion_tokens": c_tokens,
        "total_tokens": p_tokens + c_tokens,
        "estimated_cost": round(cost, 2),
        "provider": "anthropic",
        "model": "claude-3.5-sonnet"
    }


if os.path.exists("frontend/dist"):
    app.mount("/", StaticFiles(directory="frontend/dist", html=True), name="frontend")


# -- Runner ------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    cfg = get_settings()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)-30s | %(levelname)-7s | %(message)s",
    )

    uvicorn.run(
        "server:app",
        host=cfg.server_host,
        port=cfg.server_port,
        reload=False,
        log_level="info",
    )
