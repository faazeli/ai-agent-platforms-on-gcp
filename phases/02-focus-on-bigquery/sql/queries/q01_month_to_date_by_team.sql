-- Q1 · Month-to-date effective cost per team and service.
-- Prunes to roughly one month of partitions.
SELECT
  x_TeamId,
  ServiceName,
  ROUND(SUM(EffectiveCost), 2) AS effective_cost
FROM finops.focus_costs
WHERE ChargePeriodStart >= TIMESTAMP_TRUNC(CURRENT_TIMESTAMP(), MONTH)
GROUP BY x_TeamId, ServiceName
ORDER BY effective_cost DESC;
