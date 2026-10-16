-- Q4 · Share of spend with no owning team (tagging hygiene), per month.
-- A FinOps team usually sets a target such as "under 5% untagged".
SELECT
  DATE(BillingPeriodStart) AS billing_month,
  ROUND(SUM(IF(x_TeamId IS NULL, EffectiveCost, 0)), 2) AS untagged_cost,
  ROUND(SUM(EffectiveCost), 2) AS total_cost,
  ROUND(SAFE_DIVIDE(SUM(IF(x_TeamId IS NULL, EffectiveCost, 0)), SUM(EffectiveCost)) * 100, 2) AS untagged_pct
FROM finops.focus_costs
WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 6 MONTH))
GROUP BY billing_month
ORDER BY billing_month;
