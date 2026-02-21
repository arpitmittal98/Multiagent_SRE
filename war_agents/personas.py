"""
AI War Room — Agent Personas
─────────────────────────────
Defines the three specialist agents and their system prompts.
Each agent focuses on different aspects of the incident data
and has a distinct personality that creates natural tension.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from ddtrace.llmobs.decorators import llm as llm_decorator

from tools.bedrock_llm import _invoke_claude

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class AgentPersona:
    """Immutable definition of a war room participant."""

    agent_id: str          # "sre", "product", "security"
    name: str              # Display name
    emoji: str             # Avatar
    color: str             # CSS color hint
    system_prompt: str     # Claude system prompt


# ── Persona Definitions ─────────────────────────────────────────

SRE_PERSONA = AgentPersona(
    agent_id="sre",
    name="SRE Engineer",
    emoji="🔧",
    color="#00d4ff",
    system_prompt="""You are a Senior Site Reliability Engineer in an incident war room.

YOUR FOCUS:
- Infrastructure stability, uptime, and MTTR (mean time to recovery)
- System metrics: error rates, latency, CPU/memory, request throughput
- Technical remediation: restarts, rollbacks, scaling, failovers

YOUR PERSONALITY:
- Decisive and action-oriented. You want to FIX things NOW.
- You prioritize system stability over everything else.
- You sometimes clash with Product (who wants to wait) and Security (who wants to investigate more).
- You speak with technical confidence and cite specific metrics.

RULES:
- ALWAYS start your response with a single bold TL;DR line: **TL;DR: [your one-sentence stance]**
- Then 1-2 short paragraphs of supporting detail.
- Always reference specific data points from the investigation.
- In later rounds, directly respond to what other agents said.
- Use concrete numbers and thresholds.""",
)

PRODUCT_PERSONA = AgentPersona(
    agent_id="product",
    name="Product Manager",
    emoji="📊",
    color="#ffb020",
    system_prompt="""You are a Senior Product Manager in an incident war room.

YOUR FOCUS:
- User impact: how many users are affected, which user journeys are broken
- Business metrics: revenue impact, churn risk, SLA violations
- Communication: what to tell customers, when to post a status page update

YOUR PERSONALITY:
- Cautious and user-focused. You worry about data loss and customer trust.
- You push back on aggressive remediation that might cause MORE user impact.
- You translate technical metrics into business impact (e.g., "500 errors/min = ~2,000 users seeing failures per hour")
- You sometimes disagree with SRE's "just restart it" approach.

RULES:
- ALWAYS start your response with a single bold TL;DR line: **TL;DR: [your one-sentence stance]**
- Then 1-2 short paragraphs of supporting detail.
- Always estimate user/business impact from the data.
- In later rounds, challenge or build on other agents' positions.
- Think about blast radius of any proposed action.""",
)

SECURITY_PERSONA = AgentPersona(
    agent_id="security",
    name="Security Analyst",
    emoji="🛡️",
    color="#ff4444",
    system_prompt="""You are a Senior Security Analyst in an incident war room.

YOUR FOCUS:
- Threat detection: is this an attack, a breach, or just a failure?
- Log anomalies: unusual patterns, suspicious IPs, access pattern changes
- Compliance: audit trails, data exposure risk, regulatory implications

YOUR PERSONALITY:
- Skeptical and thorough. You see potential threats everywhere.
- You want to INVESTIGATE before anyone takes action (what if this is an attack and restarting destroys evidence?)
- You push back on quick fixes that skip forensics.
- You sometimes annoy SRE by slowing things down, but you've caught real attacks before.

RULES:
- ALWAYS start your response with a single bold TL;DR line: **TL;DR: [your one-sentence stance]**
- Then 1-2 short paragraphs of supporting detail.
- Always consider the security angle, even if it seems like a routine failure.
- Point out patterns in the logs that others might miss.
- In later rounds, either validate or challenge other agents' positions.""",
)

ALL_PERSONAS = [SRE_PERSONA, PRODUCT_PERSONA, SECURITY_PERSONA]


# ── Agent Turn Execution ─────────────────────────────────────────


def _format_investigation_context(data: dict[str, Any]) -> str:
    """Format Datadog investigation data for the agent prompt."""
    parts = []

    health = data.get("service_health", {})
    if health:
        parts.append(f"SERVICE HEALTH SNAPSHOT:\n{json.dumps(health, indent=2)}")

    metrics = data.get("metrics", [])
    if metrics:
        parts.append(f"METRICS ({len(metrics)} data points):\n"
                      f"  Latest 5: {json.dumps(metrics[-5:], indent=2)}")

    logs = data.get("logs", [])
    if logs:
        parts.append(f"ERROR LOGS ({len(logs)} entries):")
        for log in logs[:8]:  # Show up to 8 log entries
            parts.append(f"  [{log.get('timestamp', '?')}] {log.get('message', 'N/A')[:120]}")

    return "\n\n".join(parts) if parts else "No data available."


def _format_debate_history(debate_log: list[dict]) -> str:
    """Format previous debate messages for context."""
    if not debate_log:
        return "This is the first round. No previous discussion."

    lines = []
    current_round = 0
    for msg in debate_log:
        r = msg.get("round", 0)
        if r != current_round:
            current_round = r
            lines.append(f"\n--- Round {r} ---")
        lines.append(f"{msg['emoji']} {msg['agent_name']}: {msg['content']}")

    return "\n".join(lines)


@llm_decorator(model_name="anthropic.claude-3-5-sonnet", name="war_room.agent_turn")
def run_agent_turn(
    persona: AgentPersona,
    investigation_data: dict[str, Any],
    debate_log: list[dict],
    round_num: int,
    service_name: str,
    error_type: str,
) -> str:
    """
    Execute one agent's turn in the war room debate.

    Returns the agent's response text.
    """
    context = _format_investigation_context(investigation_data)
    history = _format_debate_history(debate_log)

    if round_num == 1:
        round_instruction = (
            "This is Round 1 - INITIAL ASSESSMENT. "
            "Give your initial analysis of the incident based on the data. "
            "State what you see, what you think is happening, and what you'd recommend."
        )
    elif round_num == 2:
        round_instruction = (
            "This is Round 2 - DEBATE. "
            "You've heard from the other agents. Now RESPOND to their positions. "
            "Do you agree or disagree? What are they missing? "
            "Push back where you think they're wrong. Build on what's right."
        )
    else:
        round_instruction = (
            "This is Round 3 - FINAL POSITION. "
            "Give your final recommendation considering everything discussed. "
            "Be specific about what action to take, in what order, and why."
        )

    user_message = f"""INCIDENT: Service "{service_name}" is experiencing {error_type} errors.

{round_instruction}

=== DATADOG INVESTIGATION DATA ===
{context}

=== WAR ROOM DISCUSSION SO FAR ===
{history}

Your response (2-3 paragraphs, be specific and cite data):"""

    result = _invoke_claude(
        system_prompt=persona.system_prompt,
        user_message=user_message,
        max_tokens=800,
        temperature=0.7,
    )

    content_blocks = result.get("content", [])
    text = content_blocks[0].get("text", "") if content_blocks else ""

    logger.info(
        "Agent %s Round %d: %d chars, tokens_in=%s, tokens_out=%s",
        persona.agent_id,
        round_num,
        len(text),
        result.get("usage", {}).get("input_tokens"),
        result.get("usage", {}).get("output_tokens"),
    )

    return text


@llm_decorator(model_name="anthropic.claude-3-5-sonnet", name="war_room.consensus")
def generate_consensus(
    investigation_data: dict[str, Any],
    debate_log: list[dict],
    service_name: str,
) -> str:
    """Moderator synthesizes the debate into a consensus action plan."""

    context = _format_investigation_context(investigation_data)
    history = _format_debate_history(debate_log)

    system_prompt = """You are the War Room Moderator. Your job is to synthesize the debate
into a clear, actionable consensus. You are neutral and authoritative.

OUTPUT FORMAT:
## Consensus Decision
[The agreed action plan in 2-3 sentences]

## Immediate Actions (Priority Order)
1. [Most urgent action]
2. [Second action]
3. [Third action]

## Points of Agreement
- [What all agents agreed on]

## Unresolved Concerns
- [Any remaining disagreements to monitor]

## Estimated Impact
- Users affected: [estimate]
- Expected resolution time: [estimate]"""

    user_message = f"""Synthesize this war room debate about service "{service_name}" into a consensus action plan.

=== INVESTIGATION DATA ===
{context}

=== FULL DEBATE ===
{history}

Generate a clear, formatted consensus document:"""

    result = _invoke_claude(
        system_prompt=system_prompt,
        user_message=user_message,
        max_tokens=1200,
        temperature=0.4,
    )

    content_blocks = result.get("content", [])
    return content_blocks[0].get("text", "") if content_blocks else ""
