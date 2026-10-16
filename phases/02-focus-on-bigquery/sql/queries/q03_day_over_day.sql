-- Q3 · Day-over-day change in effective cost per team, last 14 days.
WITH daily AS (
  SELECT
    DATE(ChargePeriodStart) AS day,
    x_TeamId,
    SUM(EffectiveCost) AS cost
  FROM finops.focus_costs
  WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 15 DAY))
    AND ChargeCategory = 'Usage'
  GROUP BY day, x_TeamId
)
SELECT
  day,
  x_TeamId,
  ROUND(cost, 2) AS cost,
  ROUND(cost - LAG(cost) OVER w, 2) AS change,
  ROUND(SAFE_DIVIDE(cost - LAG(cost) OVER w, LAG(cost) OVER w) * 100, 1) AS change_pct
FROM daily
WINDOW w AS (PARTITION BY x_TeamId ORDER BY day)
ORDER BY x_TeamId, day;
