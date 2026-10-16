"""Tool output models. Returning these makes FastMCP publish an output schema,
so clients (and agents) receive typed JSON instead of free text."""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from pydantic import BaseModel, Field


class ServiceCost(BaseModel):
    service_name: str
    effective_cost: Decimal


class TeamCostSummary(BaseModel):
    team_id: str
    month: str
    currency: str
    total_effective_cost: Decimal
    total_billed_cost: Decimal
    top_services: list[ServiceCost]


class ResourceCost(BaseModel):
    resource_id: str
    service_name: str
    effective_cost: Decimal


class DailyCost(BaseModel):
    day: date
    effective_cost: Decimal


class TeamList(BaseModel):
    teams: list[str]


class ResourceList(BaseModel):
    team_id: str
    month: str
    resources: list[ResourceCost] = Field(description="Most expensive first")


class Anomaly(BaseModel):
    day: date
    effective_cost: Decimal
    trailing_mean: Decimal
    z_score: float = Field(description="Standard deviations above the trailing mean")


class AnomalyReport(BaseModel):
    team_id: str
    window_start: date
    window_end: date
    threshold: float
    anomalies: list[Anomaly] = Field(description="Largest z-score first; empty means nothing unusual")
