"""Configuration from environment variables (prefix COST_API_). No secrets in code."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Annotated, Literal

from pydantic import field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

SAMPLE_RELATIVE = Path("data/sample/focus_costs.csv")


def find_sample_csv() -> Path:
    """Find the course's sample data by walking up from the CWD and from this file."""
    for start in (Path.cwd(), Path(__file__).resolve().parent):
        for folder in (start, *start.parents):
            candidate = folder / SAMPLE_RELATIVE
            if candidate.exists():
                return candidate
    return SAMPLE_RELATIVE  # surfaced as a clear error at startup


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="COST_API_", env_file=".env", extra="ignore")

    data_source: Literal["memory", "bigquery"] = "memory"
    sample_csv: Path = find_sample_csv()
    gcp_project: str | None = None
    bq_dataset: str = "finops"
    bq_table: str = "focus_costs"
    bq_max_bytes_billed: int = 1_000_000_000  # 1 GB ceiling per query: a cost guardrail
    problem_base_url: str = "https://example.com/problems"
    default_currency: str = "USD"

    # --- Phase 6: Zero Trust ---------------------------------------------------
    # Auth is ON by default. Turn it off only for local development.
    auth_enabled: bool = True
    oidc_issuer: str = "https://idp.example.com"          # your identity provider
    oidc_audience: str = "cost-api"
    oidc_jwks_uri: str | None = None                      # e.g. https://<idp>/.well-known/jwks.json
    workload_audience: str = "https://cost-api.internal"  # what callers' Google ID tokens target
    # Comma-separated in the environment: "mcp-finops-gsa@p.iam.gserviceaccount.com,other@..."
    trusted_delegators: Annotated[list[str], NoDecode] = []
    audit_chain_id: str = "cost-api"                      # set to the pod name on GKE

    @field_validator("trusted_delegators", mode="before")
    @classmethod
    def split_commas(cls, value):
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
