"""
SRE AI Agent — Configuration Management
────────────────────────────────────────
Loads all environment variables via Pydantic Settings
and exposes a singleton config object.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings
from pydantic import Field


class Settings(BaseSettings):
    """Application settings loaded from environment / .env file."""

    # ── Datadog ──────────────────────────────────────────────
    dd_api_key: str = Field(..., description="Datadog API key")
    dd_app_key: str = Field(..., description="Datadog Application key")
    dd_site: str = Field("datadoghq.com", description="Datadog site URL")
    dd_service: str = Field("sre-ai-agent", description="Service name for traces")
    dd_env: str = Field("production", description="Environment tag")

    # ── AWS / Bedrock ────────────────────────────────────────
    aws_region: str = Field("us-east-1", description="AWS region")
    aws_access_key_id: str = Field("", description="AWS access key (optional if using IAM roles)")
    aws_secret_access_key: str = Field("", description="AWS secret key (optional if using IAM roles)")
    aws_session_token: str = Field("", description="AWS session token (for temporary STS credentials)")
    bedrock_model_id: str = Field(
        "anthropic.claude-3-5-sonnet-20241022-v2:0",
        description="Bedrock model identifier",
    )

    # ── Strands ──────────────────────────────────────────────
    strands_api_key: str = Field("", description="Strands Agents API key")

    # ── Server ───────────────────────────────────────────────
    server_host: str = Field("0.0.0.0", description="Server bind host")
    server_port: int = Field(8000, description="Server bind port")

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "case_sensitive": False,
        "extra": "ignore",
    }


@lru_cache
def get_settings() -> Settings:
    """Return a cached Settings singleton."""
    return Settings()
