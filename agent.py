"""
AI War Room -- LangGraph Orchestrator
--------------------------------------
Multi-agent debate graph where three AI specialists
(SRE, Product, Security) analyze an incident from
different angles and debate the best course of action.

Graph flow:
    gather_intel -> round_1 -> round_2 -> consensus -> summary -> END
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone
from typing import Any

from ddtrace.llmobs.decorators import workflow
from langgraph.graph import END, StateGraph

from state import WarRoomState, DebateMessage, StreamMessage
from tools.datadog_mcp import query_metrics, search_logs, get_service_health
from war_agents.personas import (
    ALL_PERSONAS,
    SRE_PERSONA,
    PRODUCT_PERSONA,
    SECURITY_PERSONA,
    run_agent_turn,
    generate_consensus,
)
from tools.bedrock_llm import _invoke_claude

logger = logging.getLogger(__name__)


# -- Utility ---------------------------------------------------------


def _emit(
    state: WarRoomState,
    step: str,
    msg_type: str,
    content: str,
    agent: str = "system",
    agent_name: str = "System",
    emoji: str = "",
) -> None:
    """Append a stream message to state for the SSE layer."""
    if "messages" not in state or state["messages"] is None:
        state["messages"] = []
    msg = StreamMessage(
        step=step,
        type=msg_type,
        agent=agent,
        agent_name=agent_name,
        emoji=emoji,
        content=content,
    )
    state["messages"].append(msg)
    state["current_step"] = step

    if "ui_queue" in state and state["ui_queue"] is not None:
        try:
            state["ui_queue"].put_nowait({"event": "message", "data": msg})
        except Exception:
            pass


def _add_debate_msg(
    state: WarRoomState,
    persona,
    round_num: int,
    content: str,
) -> None:
    """Append a debate message and also emit it as an SSE event."""
    if "debate_log" not in state or state["debate_log"] is None:
        state["debate_log"] = []

    msg = DebateMessage(
        agent=persona.agent_id,
        agent_name=persona.name,
        emoji=persona.emoji,
        round=round_num,
        content=content,
        timestamp=datetime.now(timezone.utc).isoformat(),
    )
    state["debate_log"].append(msg)

    # Also emit as SSE for the frontend
    _emit(
        state,
        step=f"round_{round_num}",
        msg_type="agent_message",
        content=content,
        agent=persona.agent_id,
        agent_name=persona.name,
        emoji=persona.emoji,
    )


# -- Graph Nodes ------------------------------------------------------


@workflow(name="warroom.gather_intel")
async def gather_intel(state: WarRoomState) -> WarRoomState:
    """
    Step 0 -- Query Datadog for metrics, logs, and service health.
    This data is shared across all agents.
    """
    service = state["service_name"]
    error = state["error_type"]

    _emit(state, "gather", "system", f"Gathering intelligence on {service}...")

    metrics, logs, health = await asyncio.gather(
        query_metrics(service),
        search_logs(service, error_type=error),
        get_service_health(service),
    )

    investigation = {
        "metrics": metrics,
        "logs": logs,
        "service_health": health,
        "error_count": len(logs),
        "time_range": "last_1h",
    }

    state["investigation_data"] = investigation
    state["debate_log"] = []

    _emit(
        state, "gather", "system",
        f"Intel gathered: {len(logs)} error logs, {len(metrics)} metric points. "
        f"Error rate: {health.get('error_rate', 'N/A')}. "
        f"War room is now active.",
    )

    return state


@workflow(name="warroom.round_1")
async def round_1(state: WarRoomState) -> WarRoomState:
    """
    Round 1 -- Each agent gives their initial assessment.
    """
    _emit(state, "round_1", "system",
          "--- ROUND 1: INITIAL ASSESSMENT ---",
          emoji="1")

    loop = asyncio.get_event_loop()

    for persona in ALL_PERSONAS:
        _emit(state, "round_1", "thought",
              f"{persona.emoji} {persona.name} is analyzing...",
              agent=persona.agent_id,
              agent_name=persona.name,
              emoji=persona.emoji)

        response = await loop.run_in_executor(
            None,
            run_agent_turn,
            persona,
            state["investigation_data"],
            state["debate_log"],
            1,
            state["service_name"],
            state["error_type"],
        )

        _add_debate_msg(state, persona, 1, response)

    return state


@workflow(name="warroom.round_2")
async def round_2(state: WarRoomState) -> WarRoomState:
    """
    Round 2 -- Agents respond to each other, debate, and challenge.
    """
    _emit(state, "round_2", "system",
          "--- ROUND 2: DEBATE & CHALLENGE ---",
          emoji="2")

    loop = asyncio.get_event_loop()

    for persona in ALL_PERSONAS:
        _emit(state, "round_2", "thought",
              f"{persona.emoji} {persona.name} is responding to the discussion...",
              agent=persona.agent_id,
              agent_name=persona.name,
              emoji=persona.emoji)

        response = await loop.run_in_executor(
            None,
            run_agent_turn,
            persona,
            state["investigation_data"],
            state["debate_log"],
            2,
            state["service_name"],
            state["error_type"],
        )

        _add_debate_msg(state, persona, 2, response)

    return state


@workflow(name="warroom.consensus")
async def consensus_node(state: WarRoomState) -> WarRoomState:
    """
    Round 3 -- Moderator synthesizes the debate into consensus.
    """
    _emit(state, "consensus", "system",
          "--- CONSENSUS: MODERATOR SYNTHESIS ---",
          agent="moderator",
          agent_name="War Room Moderator",
          emoji="--")

    loop = asyncio.get_event_loop()

    result = await loop.run_in_executor(
        None,
        generate_consensus,
        state["investigation_data"],
        state["debate_log"],
        state["service_name"],
    )

    state["consensus"] = result

    _emit(
        state, "consensus", "agent_message",
        result,
        agent="moderator",
        agent_name="War Room Moderator",
        emoji="--",
    )

    return state


@workflow(name="warroom.summary")
async def summary_node(state: WarRoomState) -> WarRoomState:
    """
    Final step -- Generate a structured war room summary report.
    """
    _emit(state, "summary", "system", "Generating war room summary report...")

    loop = asyncio.get_event_loop()

    system_prompt = """You are a technical writer producing a concise War Room Summary.
Write a markdown-formatted summary of the incident debate and resolution.
Include: incident overview, key findings from each agent, final consensus, and next steps."""

    debate_text = "\n".join(
        f"{m['emoji']} {m['agent_name']} (R{m['round']}): {m['content']}"
        for m in state.get("debate_log", [])
    )

    user_message = f"""Summarize this war room session for service "{state['service_name']}":

DEBATE:
{debate_text}

CONSENSUS:
{state.get('consensus', 'No consensus reached.')}

Write a concise markdown summary report:"""

    result = await loop.run_in_executor(
        None,
        _invoke_claude,
        system_prompt,
        user_message,
        1500,
        0.4,
    )

    content_blocks = result.get("content", [])
    report = content_blocks[0].get("text", "") if content_blocks else ""

    state["war_room_summary"] = report

    _emit(state, "summary", "result", "War room session complete.")

    return state


# -- Graph Construction -----------------------------------------------


def create_war_room_graph() -> StateGraph:
    """
    Build and compile the LangGraph war room state machine.
    """
    graph = StateGraph(WarRoomState)

    graph.add_node("gather_intel", gather_intel)
    graph.add_node("round_1", round_1)
    graph.add_node("round_2", round_2)
    graph.add_node("consensus", consensus_node)
    graph.add_node("summary", summary_node)

    graph.set_entry_point("gather_intel")
    graph.add_edge("gather_intel", "round_1")
    graph.add_edge("round_1", "round_2")
    graph.add_edge("round_2", "consensus")
    graph.add_edge("consensus", "summary")
    graph.add_edge("summary", END)

    return graph.compile()


# -- Entry Point -------------------------------------------------------


@workflow(name="war_room.run")
async def run_war_room(
    service_name: str,
    error_type: str = "500",
    ui_queue: Any = None,
) -> WarRoomState:
    """
    Top-level entry point. Builds the graph, seeds the initial
    state, and runs the full multi-agent war room pipeline.
    """
    logger.info("Starting War Room for %s -- %s", service_name, error_type)

    initial_state: WarRoomState = {
        "service_name": service_name,
        "error_type": error_type,
        "investigation_data": {},
        "debate_log": [],
        "consensus": "",
        "war_room_summary": "",
        "messages": [],
        "current_step": "initializing",
        "ui_queue": ui_queue,
    }

    graph = create_war_room_graph()
    final_state = await graph.ainvoke(initial_state)

    logger.info(
        "War Room complete -- %d messages, %d debate entries",
        len(final_state.get("messages", [])),
        len(final_state.get("debate_log", [])),
    )
    return final_state
