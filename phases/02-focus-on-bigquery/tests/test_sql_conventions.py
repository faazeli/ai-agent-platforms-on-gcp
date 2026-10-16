"""Guardrails for the warehouse, checked offline.

These are the same rules a reviewer would enforce on a PR touching SQL:
the table is partitioned, clustered and requires a partition filter, every
analyst query filters on the partition column, and the sample data matches
the FOCUS columns the DDL declares. Run from this phase's folder: pytest -q
"""

import csv
import re
from decimal import Decimal
from pathlib import Path

PHASE = Path(__file__).resolve().parents[1]
ROOT = PHASE.parents[1]
SQL = PHASE / "sql"
QUERIES = sorted((SQL / "queries").glob("*.sql"))


def strip_comments(sql: str) -> str:
    return re.sub(r"--[^\n]*", "", sql)


def ddl_columns() -> list[str]:
    ddl = strip_comments((SQL / "01_dataset_and_table.sql").read_text())
    body = ddl.split("CREATE TABLE IF NOT EXISTS finops.focus_costs (", 1)[1].split("\n)\n", 1)[0]
    return [line.split()[0] for line in body.strip().splitlines() if line.strip()]


def test_table_is_partitioned_clustered_and_guarded():
    ddl = strip_comments((SQL / "01_dataset_and_table.sql").read_text())
    assert "PARTITION BY DATE(ChargePeriodStart)" in ddl
    assert "CLUSTER BY x_TeamId, ServiceName, SubAccountId" in ddl
    assert "require_partition_filter = TRUE" in ddl


def test_custom_columns_use_the_x_prefix():
    focus = {"BillingAccountId", "SubAccountId", "ServiceProviderName", "ServiceName", "ServiceCategory",
             "ChargeCategory", "ChargePeriodStart", "ChargePeriodEnd", "BillingPeriodStart", "BilledCost",
             "EffectiveCost", "ListCost", "BillingCurrency", "RegionId", "ResourceId", "Tags"}
    for column in ddl_columns():
        assert column in focus or column.startswith("x_"), f"{column} is not FOCUS and lacks the x_ prefix"


def test_there_are_at_least_six_analyst_queries():
    assert len(QUERIES) >= 6


def test_every_query_filters_on_the_partition_column():
    for path in QUERIES:
        where_clauses = re.findall(r"WHERE(.*?)(?:GROUP BY|ORDER BY|$)", strip_comments(path.read_text()), re.S)
        assert any("ChargePeriodStart >=" in w for w in where_clauses), f"{path.name} has no partition filter"


def test_queries_use_parameters_not_literals_for_teams():
    for path in QUERIES:
        sql = strip_comments(path.read_text())
        assert not re.search(r"x_TeamId\s*=\s*'", sql), f"{path.name} hardcodes a team; use @team_id"


def test_sample_csv_matches_ddl_columns_and_money_is_exact():
    sample = ROOT / "data" / "sample" / "focus_costs.csv"
    with sample.open(newline="") as f:
        reader = csv.DictReader(f)
        assert reader.fieldnames == ddl_columns()
        for row in reader:
            for money in ("BilledCost", "EffectiveCost", "ListCost"):
                Decimal(row[money])  # raises if not an exact decimal string


def test_sample_has_the_teaching_features():
    with (ROOT / "data" / "sample" / "focus_costs.csv").open(newline="") as f:
        rows = list(csv.DictReader(f))
    assert any(r["ChargeCategory"] == "Purchase" for r in rows), "commitment purchase rows"
    assert any(r["x_TeamId"] == "" for r in rows), "untagged spend"
    assert any(r["BilledCost"] == "0.0000" and Decimal(r["EffectiveCost"]) > 0 for r in rows), "covered usage"
