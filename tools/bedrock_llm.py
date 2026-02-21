"""
SRE AI Agent — Amazon Bedrock LLM Integration
──────────────────────────────────────────────
Wraps boto3 Bedrock Runtime calls to Claude 3.5 Sonnet
for root-cause analysis and report generation.

The ``@LLMObs.llm()`` decorator captures prompt / completion
pairs, token usage, latency, and model metadata inside
Datadog LLM Observability.
"""

from __future__ import annotations

import json
import logging
from typing import Any

import boto3
from ddtrace.llmobs.decorators import llm

from config import get_settings

logger = logging.getLogger(__name__)

# ── Client factory ───────────────────────────────────────────────

_bedrock_client = None


def _get_client():
    """Lazily create a Bedrock Runtime client."""
    global _bedrock_client
    if _bedrock_client is None:
        cfg = get_settings()
        session_kwargs: dict[str, Any] = {"region_name": cfg.aws_region}
        if cfg.aws_access_key_id:
            session_kwargs["aws_access_key_id"] = cfg.aws_access_key_id
            session_kwargs["aws_secret_access_key"] = cfg.aws_secret_access_key
            if cfg.aws_session_token:
                session_kwargs["aws_session_token"] = cfg.aws_session_token
        session = boto3.Session(**session_kwargs)
        _bedrock_client = session.client("bedrock-runtime")
    return _bedrock_client


# ── Core call ────────────────────────────────────────────────────


def _invoke_claude(
    system_prompt: str,
    user_message: str,
    max_tokens: int = 4096,
    temperature: float = 0.3,
) -> dict[str, Any]:
    """
    Low-level invoke against Bedrock Claude.

    Returns the full API response dict.
    """
    cfg = get_settings()

    body = json.dumps(
        {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": max_tokens,
            "temperature": temperature,
            "system": system_prompt,
            "messages": [{"role": "user", "content": user_message}],
        }
    )

    logger.info(
        "Invoking Bedrock model %s  (max_tokens=%d, temp=%.1f)",
        cfg.bedrock_model_id,
        max_tokens,
        temperature,
    )

    client = _get_client()
    response = client.invoke_model(
        modelId=cfg.bedrock_model_id,
        contentType="application/json",
        accept="application/json",
        body=body,
    )

    result = json.loads(response["body"].read())
    logger.info(
        "Bedrock response: stop_reason=%s, tokens_in=%s, tokens_out=%s",
        result.get("stop_reason"),
        result.get("usage", {}).get("input_tokens"),
        result.get("usage", {}).get("output_tokens"),
    )
    return result


# ── Public API ───────────────────────────────────────────────────


@llm(model_name="claude-3.5-sonnet", model_provider="aws_bedrock")
def analyze_root_cause(investigation_data: dict[str, Any]) -> str:
    """
    Send structured Datadog telemetry to Claude 3.5 Sonnet
    and return a root-cause analysis.

    Parameters
    ----------
    investigation_data : dict
        Must contain ``metrics``, ``logs``, and ``service_status`` keys.

    Returns
    -------
    str
        A structured root-cause analysis in Markdown.
    """
    system_prompt = (
        "You are a senior Site Reliability Engineer AI assistant. "
        "Given the following observability telemetry from Datadog, "
        "perform a thorough root cause analysis. Be specific about:\n"
        "1. The most likely root cause\n"
        "2. Contributing factors\n"
        "3. Evidence from the metrics and logs that supports your conclusion\n"
        "4. Recommended remediation steps, ranked by priority\n\n"
        "Format your response in clear Markdown."
    )

    user_message = (
        "## Investigation Telemetry\n\n"
        f"```json\n{json.dumps(investigation_data, indent=2, default=str)}\n```\n\n"
        "Please analyze this data and provide your root cause assessment."
    )

    result = _invoke_claude(system_prompt, user_message)
    content_blocks = result.get("content", [])
    return content_blocks[0].get("text", "") if content_blocks else ""


@llm(model_name="claude-3.5-sonnet", model_provider="aws_bedrock")
def generate_report_text(
    service_name: str,
    error_type: str,
    root_cause: str,
    remediation_action: str,
    remediation_result: dict[str, Any],
) -> str:
    """
    Generate a creative, journalistic 'Incident News Report'.

    Returns
    -------
    str
        A Markdown-formatted incident report written in news style.
    """
    system_prompt = (
        "You are a brilliant tech journalist writing for a major tech publication. "
        "Write a compelling, creative 'Incident News Report' about a production "
        "incident that was just investigated and resolved by an AI SRE agent. "
        "Use a narrative storytelling style with:\n"
        "- A catchy headline\n"
        "- A dramatic opening paragraph\n"
        "- 'What Happened' section with timeline\n"
        "- 'The Investigation' section referencing the AI analysis\n"
        "- 'The Fix' section describing the remediation\n"
        "- 'Lessons Learned' closing section\n"
        "- Include a severity rating (Critical / High / Medium / Low)\n\n"
        "Keep it professional but engaging. Format in Markdown."
    )

    user_message = (
        f"**Service:** {service_name}\n"
        f"**Error Type:** {error_type}\n\n"
        f"## Root Cause Analysis\n{root_cause}\n\n"
        f"## Remediation\n"
        f"**Action Taken:** {remediation_action}\n"
        f"**Result:** {json.dumps(remediation_result, indent=2, default=str)}\n"
    )

    result = _invoke_claude(
        system_prompt, user_message, max_tokens=4096, temperature=0.7
    )
    content_blocks = result.get("content", [])
    return content_blocks[0].get("text", "") if content_blocks else ""


def generate_synthetic_logs(
    scenario: str,
    service_name: str,
    log_count: int = 47,
) -> list[dict[str, Any]]:
    """
    Uses Claude 3.5 Sonnet to 'hallucinate' highly realistic application logs
    and stack traces for a given incident scenario.

    Parameters
    ----------
    scenario : str
        Description of the incident (e.g., "A massive database deadlock")
    service_name : str
        Name of the affected service.
    log_count : int
        Approximate number of error messages to generate.

    Returns
    -------
    list[dict]
        A list of JSON log structures ready to be sent to Datadog.
    """
    system_prompt = (
        "You are an expert Systems Engineer and Chaos Engineering tool. "
        "Your task is to generate highly realistic, deeply technical application error logs "
        "and stack traces based on a provided incident scenario.\n\n"
        "Generate exactly " + str(log_count) + " unique log entries in a pure JSON array format.\n"
        "Each log entry must have this exact structure:\n"
        "{\n"
        "  \"message\": \"<the main error message or stack trace>\",\n"
        "  \"status\": \"error\",\n"
        "  \"http_status\": \"<e.g. 500 or 503>\",\n"
        "  \"path\": \"<e.g. /api/v1/checkout>\",\n"
        "  \"kind\": \"<e.g. OperationalError or TimeoutError>\"\n"
        "}\n\n"
        "REQUIREMENTS:\n"
        "- The messages must be technically accurate for the scenario described.\n"
        "- Include realistic file paths, line numbers, and variable names in stack traces.\n"
        "- Only return valid JSON. Do not include markdown formatting or explanations."
    )

    user_message = (
        f"**Service:** {service_name}\n"
        f"**Scenario:** {scenario}\n\n"
        f"Please generate {log_count} realistic error logs for this scenario."
    )

    result = _invoke_claude(
        system_prompt, user_message, max_tokens=4096, temperature=0.8
    )
    content_blocks = result.get("content", [])
    raw_text = content_blocks[0].get("text", "[]") if content_blocks else "[]"
    
    # Clean up potentially markdown-wrapped JSON
    if raw_text.startswith("```json"):
        raw_text = raw_text.split("```json")[1]
    if raw_text.endswith("```"):
        raw_text = raw_text.rsplit("```", 1)[0]
    
    try:
        logs = json.loads(raw_text.strip())
        if not isinstance(logs, list):
            return []
        return logs
    except json.JSONDecodeError:
        logger.error("Failed to parse Bedrock JSON response: %s", raw_text)
        return []
