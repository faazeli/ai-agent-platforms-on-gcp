from decimal import Decimal

import pytest
from pydantic import ValidationError

from cost_api.models import CostRecord

VALID = {
    "BillingAccountId": "0A1B2C-3D4E5F-6A7B8C",
    "SubAccountId": "pay-prod-4411",
    "ServiceName": "Cloud Run",
    "ServiceCategory": "Compute",
    "ChargeCategory": "Usage",
    "ChargePeriodStart": "2026-09-01T00:00:00Z",
    "ChargePeriodEnd": "2026-09-02T00:00:00Z",
    "BilledCost": "12.3400",
    "EffectiveCost": "12.3400",
    "BillingCurrency": "USD",
    "Tags": '{"team":"payments"}',
    "x_TeamId": "payments",
}


def test_accepts_focus_names_and_serializes_snake_case():
    record = CostRecord.model_validate(VALID)
    assert record.effective_cost == Decimal("12.34")
    assert record.tags == {"team": "payments"}
    dumped = record.model_dump()
    assert "effective_cost" in dumped and "EffectiveCost" not in dumped


def test_accepts_snake_case_names_too():
    record = CostRecord.model_validate(CostRecord.model_validate(VALID).model_dump())
    assert record.team_id == "payments"


def test_money_is_decimal_not_float():
    record = CostRecord.model_validate(VALID | {"EffectiveCost": "0.1", "BilledCost": "0.2"})
    assert record.effective_cost + record.billed_cost == Decimal("0.3")  # would fail with floats


def test_empty_strings_become_none():
    record = CostRecord.model_validate(VALID | {"SubAccountId": "", "x_TeamId": "", "Tags": ""})
    assert record.sub_account_id is None and record.team_id is None and record.tags == {}


@pytest.mark.parametrize(
    "override",
    [
        {"BillingCurrency": "usd"},
        {"ChargeCategory": "Refund"},
        {"EffectiveCost": "not-a-number"},
        {"ServiceName": ""},
    ],
)
def test_rejects_bad_values(override):
    with pytest.raises(ValidationError) as err:
        CostRecord.model_validate(VALID | override)
    # Errors name the field the way the caller sent it (the FOCUS column name).
    assert err.value.errors()[0]["loc"] == (next(iter(override)),)


def test_rejects_end_before_start():
    with pytest.raises(ValidationError, match="ChargePeriodEnd must be after"):
        CostRecord.model_validate(VALID | {"ChargePeriodEnd": "2026-08-31T00:00:00Z"})


def test_json_schema_is_available_for_llm_tools():
    # "validation" mode describes inputs (FOCUS names); "serialization" describes outputs.
    assert "ChargeCategory" in CostRecord.model_json_schema()["properties"]
    out = CostRecord.model_json_schema(mode="serialization")
    assert out["properties"]["charge_category"]["enum"][0] == "Usage"
