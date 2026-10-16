"""Configuration from environment variables (prefix MCP_FINOPS_)."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MCP_FINOPS_", env_file=".env", extra="ignore")

    cost_api_url: str = "http://localhost:8000"
    cost_api_timeout_seconds: float = 10.0
    host: str = "0.0.0.0"
    port: int = 8001
    problem_base_url: str = "https://example.com/problems"

    # --- Phase 6 -------------------------------------------------------------
    auth_enabled: bool = True
    oidc_issuer: str = "https://idp.example.com"
    oidc_audience: str = "mcp-finops"           # tokens must be minted FOR this server (no passthrough)
    oidc_jwks_uri: str | None = None
    cost_api_audience: str = "https://cost-api.internal"  # audience of our Google ID token to cost-api
