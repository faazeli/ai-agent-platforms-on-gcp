-- Q2 · Top 10 resources for one team in one month.
-- Parameters: @team_id STRING, @month DATE (first day of the month)
--   bq query --use_legacy_sql=false \
--     --parameter=team_id:STRING:payments --parameter=month:DATE:2026-09-01 < q02_top_resources.sql
SELECT
  ResourceId,
  ServiceName,
  ROUND(SUM(EffectiveCost), 2) AS effective_cost
FROM finops.focus_costs
WHERE ChargePeriodStart >= TIMESTAMP(@month)
  AND ChargePeriodStart <  TIMESTAMP(DATE_ADD(@month, INTERVAL 1 MONTH))
  AND x_TeamId = @team_id
  AND ResourceId IS NOT NULL
GROUP BY ResourceId, ServiceName
ORDER BY effective_cost DESC
LIMIT 10;
