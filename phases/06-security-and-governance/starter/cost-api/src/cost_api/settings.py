"""Configuration from environment variables (prefix COST_API_). No secrets in code."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict

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

    # TODO Lab 6.6: add auth_enabled (default True), oidc_issuer, oidc_audience,
    #   oidc_jwks_uri, workload_audience, trusted_delegators and audit_chain_id
    #   (see security.py for how they are used). Make trusted_delegators accept a
    #   comma-separated env value: Annotated[list[str], NoDecode] plus a
    #   @field_validator(mode="before") that splits on commas.


@lru_cache
def get_settings() -> Settings:
    return Settings()
