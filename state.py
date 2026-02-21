"""
AI War Room — LangGraph State Definitions
──────────────────────────────────────────
Central TypedDict that flows through every node in the
multi-agent debate graph.
"""

from __future__ import annotations

from typing import Any, TypedDict


class InvestigationData(TypedDict, total=False):
    """Structured telemetry retrieved from Datadog."""

    metrics: list[dict[str, Any]]
    logs: list[dict[str, Any]]
    service_health: dict[str, Any]
    error_count: int
    time_range: str


class DebateMessage(TypedDict):
    """A single message in the war room debate."""

    agent: str           # "sre" | "product" | "security" | "moderator"
    agent_name: str      # "SRE Engineer" | "Product Manager" | "Security Analyst"
    emoji: str           # agent avatar emoji
    round: int           # 1, 2, or 3
    content: str
    timestamp: str


class StreamMessage(TypedDict):
    """A single message emitted to the frontend via SSE."""

    step: str            # "gather", "round_1", "round_2", "consensus", "summary"
    type: str            # "thought" | "agent_message" | "result" | "system"
    agent: str           # which agent is speaking (or "system")
    agent_name: str
    emoji: str
    content: str


class WarRoomState(TypedDict, total=False):
    """
    The master state for the LangGraph War Room.

    Three AI agents (SRE, Product, Security) debate an incident
    across multiple rounds, then a moderator synthesizes consensus.
    """

    # -- Inputs --
    service_name: str
    error_type: str

    # -- Investigation (Datadog) --
    investigation_data: InvestigationData

    # -- Debate --
    debate_log: list[DebateMessage]

    # -- Outputs --
    consensus: str
    war_room_summary: str

    # -- Streaming / UI --
    messages: list[StreamMessage]
    current_step: str
    ui_queue: Any
