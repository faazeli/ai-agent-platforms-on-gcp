-- Phase 2 · Lab 2.3 — Idempotent load from a staging table.
--
-- 1. `bq load` puts the raw CSV into finops.stg_focus_costs (all STRING columns,
--    see scripts/load_sample.sh).
-- 2. This MERGE casts, derives x_TeamId from Tags, and upserts into focus_costs.
--
-- Running it twice gives the same result: the natural key below identifies a row.
-- That property is what makes reloads, backfills and retries safe.

MERGE finops.focus_costs AS t
USING (
  SELECT
    BillingAccountId,
    NULLIF(SubAccountId, '')                       AS SubAccountId,
    NULLIF(ServiceProviderName, '')                AS ServiceProviderName,
    ServiceName,
    NULLIF(ServiceCategory, '')                    AS ServiceCategory,
    ChargeCategory,
    TIMESTAMP(ChargePeriodStart)                   AS ChargePeriodStart,
    TIMESTAMP(ChargePeriodEnd)                     AS ChargePeriodEnd,
    TIMESTAMP(NULLIF(BillingPeriodStart, ''))      AS BillingPeriodStart,
    CAST(BilledCost AS NUMERIC)                    AS BilledCost,
    CAST(EffectiveCost AS NUMERIC)                 AS EffectiveCost,
    SAFE_CAST(NULLIF(ListCost, '') AS NUMERIC)     AS ListCost,
    BillingCurrency,
    NULLIF(RegionId, '')                           AS RegionId,
    NULLIF(ResourceId, '')                         AS ResourceId,
    SAFE.PARSE_JSON(NULLIF(Tags, ''))              AS Tags,
    -- Prefer an explicit team column; fall back to the "team" tag.
    COALESCE(NULLIF(x_TeamId, ''),
             JSON_VALUE(SAFE.PARSE_JSON(NULLIF(Tags, '')), '$.team')) AS x_TeamId
  FROM finops.stg_focus_costs
) AS s
ON  t.ChargePeriodStart = s.ChargePeriodStart
AND t.BillingAccountId  = s.BillingAccountId
AND t.ChargeCategory    = s.ChargeCategory
AND IFNULL(t.ResourceId, '') = IFNULL(s.ResourceId, '')
AND IFNULL(t.SubAccountId, '') = IFNULL(s.SubAccountId, '')
AND t.ServiceName       = s.ServiceName
-- The partition filter on the target keeps the MERGE from scanning every partition.
AND t.ChargePeriodStart >= TIMESTAMP('2000-01-01')
WHEN MATCHED THEN UPDATE SET
  BilledCost = s.BilledCost,
  EffectiveCost = s.EffectiveCost,
  ListCost = s.ListCost,
  Tags = s.Tags,
  x_TeamId = s.x_TeamId
WHEN NOT MATCHED THEN INSERT ROW;
