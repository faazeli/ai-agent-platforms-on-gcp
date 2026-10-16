"""Domain and API models for cost-api.

Input uses FOCUS column names (validation aliases); output uses snake_case,
which is the contract our own API publishes. Money is always Decimal.
"""

from __future__ import annotations

import json  # noqa: F401  (you will need it in Lab 1.1)
from datetime import date, datetime
from decimal import Decimal
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ChargeCategory = Literal["Usage", "Purchase", "Tax", "Credit", "Adjustment"]

# FOCUS ServiceCategory allowed values we expect in this course's data.
ServiceCategory = Literal[
    "AI and Machine Learning",
    "Analytics",
    "Business Applications",
    "Compute",
    "Databases",
    "Developer Tools",
    "Multicloud",
    "Identity",
    "Integration",
    "Internet of Things",
    "Management and Governance",
    "Media",
    "Migration",
    "Mobile",
    "Networking",
    "Security",
    "Storage",
    "Web",
    "Other",
]


class CostRecord(BaseModel):
    """One FOCUS cost row.

    Accepts FOCUS names (``EffectiveCost``) or snake_case names (``effective_cost``)
    on input and always serializes as snake_case.
    """

    model_config = ConfigDict(validate_by_alias=True, validate_by_name=True, frozen=True)

    billing_account_id: str = Field(validation_alias="BillingAccountId", min_length=1)
    sub_account_id: str | None = Field(default=None, validation_alias="SubAccountId")
    service_provider_name: str | None = Field(default=None, validation_alias="ServiceProviderName")
    service_name: str = Field(validation_alias="ServiceName", min_length=1)
    service_category: ServiceCategory | None = Field(default=None, validation_alias="ServiceCategory")
    charge_category: ChargeCategory = Field(validation_alias="ChargeCategory")
    charge_period_start: datetime = Field(validation_alias="ChargePeriodStart")
    charge_period_end: datetime = Field(validation_alias="ChargePeriodEnd")
    billing_period_start: datetime | None = Field(default=None, validation_alias="BillingPeriodStart")
    billed_cost: Decimal = Field(validation_alias="BilledCost", decimal_places=10)
    effective_cost: Decimal = Field(validation_alias="EffectiveCost", decimal_places=10)
    list_cost: Decimal | None = Field(default=None, validation_alias="ListCost", decimal_places=10)
    billing_currency: str = Field(validation_alias="BillingCurrency", pattern=r"^[A-Z]{3}$")
    region_id: str | None = Field(default=None, validation_alias="RegionId")
    resource_id: str | None = Field(default=None, validation_alias="ResourceId")
    tags: dict[str, str] = Field(default_factory=dict, validation_alias="Tags")
    team_id: str | None = Field(default=None, validation_alias="x_TeamId")

    # TODO Lab 1.1 (a): add a `@field_validator("*", mode="before")` that turns ""
    #   into None. CSV exports use empty strings for missing values.

    # TODO Lab 1.1 (b): add a `@field_validator("tags", mode="before")` that turns
    #   None or "" into {} and parses a JSON string such as '{"team":"payments"}'.

    # TODO Lab 1.1 (c): add a `@model_validator(mode="after")` that raises
    #   ValueError("ChargePeriodEnd must be after ChargePeriodStart") when the
    #   period is empty or reversed.


class Team(BaseModel):
    team_id: str


class ServiceCost(BaseModel):
    service_name: str
    effective_cost: Decimal


class TeamCostSummary(BaseModel):
    team_id: str
    month: str = Field(description="YYYY-MM")
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


class Page(BaseModel):
    """A page of cost records. Clients follow ``next_offset`` until it is null."""

    items: list[CostRecord]
    limit: int
    offset: int
    next_offset: int | None
