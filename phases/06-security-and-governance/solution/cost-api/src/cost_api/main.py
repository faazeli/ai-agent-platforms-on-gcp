"""cost-api: a typed HTTP API over FOCUS cost data.

Run locally:
    uvicorn cost_api.main:app --reload --app-dir src
Then open http://127.0.0.1:8000/docs
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from datetime import date
from typing import Annotated

from fastapi import Depends, FastAPI, Path, Query, Request

from costpilot_security.audit import AuditLog
from costpilot_security.problems import install_security_handlers
from costpilot_security.rbac import visible_teams

from .models import DailyCost, Page, ResourceCost, Team, TeamCostSummary
from .problems import ProblemError, install_problem_handlers
from .repository import CostRepository, InMemoryCostRepository
from .security import Caller, authorize, build_security
from .settings import Settings, get_settings

MONTH_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"
TEAM_PATTERN = r"^[a-z0-9-]{2,40}$"

TeamId = Annotated[str, Path(pattern=TEAM_PATTERN, description="Team identifier, e.g. payments")]
Month = Annotated[str, Query(pattern=MONTH_PATTERN, description="Calendar month, YYYY-MM", examples=["2026-09"])]


def build_repository(settings: Settings) -> CostRepository:
    if settings.data_source == "bigquery":
        try:
            from .bigquery_repository import BigQueryCostRepository  # added in Phase 2
        except ImportError as exc:  # pragma: no cover - depends on phase
            raise RuntimeError("The BigQuery repository is added in Phase 2.") from exc
        return BigQueryCostRepository.from_settings(settings)
    return InMemoryCostRepository.from_csv(settings.sample_csv)


def get_cost_repository(request: Request) -> CostRepository:
    return request.app.state.repository


async def require_known_team(
    request: Request, team_id: TeamId, principal: Caller,
    repo: Annotated[CostRepository, Depends(get_cost_repository)],
) -> str:
    # Authorize BEFORE checking existence, so outsiders can't probe which teams exist.
    authorize(request, principal, "costs:read", team_id)
    if team_id not in await repo.list_teams():
        raise ProblemError(404, "team-not-found", "Unknown team",
                           f"No cost data exists for team '{team_id}'. Call GET /v1/teams for valid ids.")
    return team_id


Repo = Annotated[CostRepository, Depends(get_cost_repository)]
KnownTeam = Annotated[str, Depends(require_known_team)]


def create_app(settings: Settings | None = None, repository: CostRepository | None = None) -> FastAPI:
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.repository = repository or build_repository(settings)
        yield

    # Security is set up at creation (not in lifespan) so a misconfiguration fails at startup.
    security = build_security(settings)
    audit_log = AuditLog(settings.audit_chain_id)

    app = FastAPI(
        title="cost-api",
        version="3.0.0",
        summary="FOCUS cost data for teams. Every error is RFC 9457 Problem Details. "
                "Every request is authenticated (OIDC user token, or a workload ID token + delegation).",
        lifespan=lifespan,
    )
    install_problem_handlers(app, settings.problem_base_url)
    install_security_handlers(app, settings.problem_base_url)
    app.state.security, app.state.audit = security, audit_log

    @app.get("/healthz", tags=["ops"])
    async def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/v1/teams", response_model=list[Team], tags=["costs"])
    async def list_teams(request: Request, principal: Caller, repo: Repo):
        authorize(request, principal, "costs:read")
        return [Team(team_id=t) for t in visible_teams(principal, await repo.list_teams())]

    @app.get("/v1/teams/{team_id}/costs", response_model=Page, tags=["costs"])
    async def team_costs(
        team_id: KnownTeam,
        month: Month,
        repo: Repo,
        service: Annotated[str | None, Query(max_length=80)] = None,
        limit: Annotated[int, Query(ge=1, le=1000)] = 100,
        offset: Annotated[int, Query(ge=0)] = 0,
    ):
        items = await repo.cost_records(team_id, month, service, limit + 1, offset)
        has_more = len(items) > limit
        return Page(items=items[:limit], limit=limit, offset=offset,
                    next_offset=offset + limit if has_more else None)

    @app.get("/v1/teams/{team_id}/summary", response_model=TeamCostSummary, tags=["costs"])
    async def team_summary(team_id: KnownTeam, month: Month, repo: Repo):
        summary = await repo.team_summary(team_id, month)
        if summary is None:
            raise ProblemError(404, "no-cost-data", "No cost data for this period",
                               f"Team '{team_id}' has no cost records in {month}.")
        return summary

    @app.get("/v1/teams/{team_id}/resources", response_model=list[ResourceCost], tags=["costs"])
    async def top_resources(
        team_id: KnownTeam, month: Month, repo: Repo,
        limit: Annotated[int, Query(ge=1, le=20)] = 10,
    ):
        return await repo.top_resources(team_id, month, limit)

    @app.get("/v1/teams/{team_id}/daily", response_model=list[DailyCost], tags=["costs"])
    async def daily_costs(
        team_id: KnownTeam, repo: Repo,
        end: Annotated[date, Query(description="Last day included, YYYY-MM-DD")],
        days: Annotated[int, Query(ge=1, le=90)] = 30,
    ):
        return await repo.daily_costs(team_id, end, days)

    return app


app = create_app()
