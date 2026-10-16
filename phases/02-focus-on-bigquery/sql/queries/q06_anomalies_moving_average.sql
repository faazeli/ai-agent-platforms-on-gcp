-- Q6 · Spend anomalies: days more than 3 standard deviations above the
-- trailing 7-day mean, per team and service. This is the logic the
-- detect_anomalies MCP tool (Phase 3) exposes to agents.
WITH daily AS (
  SELECT
    DATE(ChargePeriodStart) AS day,
    x_TeamId,
    ServiceName,
    SUM(EffectiveCost) AS cost
  FROM finops.focus_costs
  WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(CURRENT_DATE(), INTERVAL 60 DAY))
    AND ChargeCategory = 'Usage'
  GROUP BY day, x_TeamId, ServiceName
),
scored AS (
  SELECT
    *,
    AVG(cost)        OVER w AS trailing_mean,
    STDDEV_SAMP(cost) OVER w AS trailing_sd
  FROM daily
  WINDOW w AS (PARTITION BY x_TeamId, ServiceName ORDER BY day ROWS BETWEEN 7 PRECEDING AND 1 PRECEDING)
)
SELECT
  day, x_TeamId, ServiceName,
  ROUND(cost, 2) AS cost,
  ROUND(trailing_mean, 2) AS trailing_mean,
  ROUND(SAFE_DIVIDE(cost - trailing_mean, trailing_sd), 1) AS z_score
FROM scored
WHERE SAFE_DIVIDE(cost - trailing_mean, trailing_sd) > 3
ORDER BY z_score DESC;
