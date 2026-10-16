-- Q5 · Commitment utilization: how much of what we bought did we use?
-- Purchase rows carry the billed commitment; covered usage rows carry its
-- amortized cost (BilledCost = 0, EffectiveCost > 0). Utilization below ~90%
-- usually means the commitment was sized too large.
-- FOCUS also defines Commitment* columns (CommitmentDiscountId, ...Status) for
-- exact attribution; this sample keeps it simpler.
WITH monthly AS (
  SELECT
    DATE(BillingPeriodStart) AS billing_month,
    x_TeamId,
    ServiceName,
    SUM(IF(ChargeCategory = 'Purchase', BilledCost, 0)) AS committed,
    SUM(IF(ChargeCategory = 'Usage' AND BilledCost = 0, EffectiveCost, 0)) AS covered_usage
  FROM finops.focus_costs
  WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 6 MONTH))
  GROUP BY billing_month, x_TeamId, ServiceName
)
SELECT
  billing_month,
  x_TeamId,
  ServiceName,
  ROUND(committed, 2) AS committed,
  ROUND(covered_usage, 2) AS covered_usage,
  ROUND(SAFE_DIVIDE(covered_usage, committed) * 100, 1) AS utilization_pct,
  ROUND(committed - covered_usage, 2) AS unused_commitment
FROM monthly
WHERE committed > 0
ORDER BY billing_month, x_TeamId;
