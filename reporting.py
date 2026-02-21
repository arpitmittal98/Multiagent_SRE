"""
SRE AI Agent — Incident Report Generator
─────────────────────────────────────────
Calls Bedrock Claude to produce a creative, journalistic
"Incident News Report" from the full agent state.
"""

from __future__ import annotations

import logging
from typing import Any

from ddtrace.llmobs.decorators import workflow

from state import SREAgentState
from tools.bedrock_llm import generate_report_text

logger = logging.getLogger(__name__)


@workflow(name="reporting.generate_incident_report")
def generate_incident_report(state: SREAgentState) -> str:
    """
    Consume the completed agent state and return a Markdown
    'Incident News Report' suitable for sharing in Slack,
    Confluence, or a dashboard.

    Parameters
    ----------
    state : SREAgentState
        Must contain ``service_name``, ``error_type``,
        ``root_cause_analysis``, ``remediation_action``,
        and ``remediation_result``.

    Returns
    -------
    str
        Markdown-formatted incident report.
    """
    logger.info(
        "Generating incident report for %s — %s",
        state.get("service_name", "unknown"),
        state.get("error_type", "unknown"),
    )

    report = generate_report_text(
        service_name=state.get("service_name", "Unknown Service"),
        error_type=state.get("error_type", "Unknown Error"),
        root_cause=state.get("root_cause_analysis", "No analysis available."),
        remediation_action=state.get("remediation_action", "None taken."),
        remediation_result=state.get("remediation_result", {}),
    )

    logger.info("Incident report generated (%d characters)", len(report))
    return report
