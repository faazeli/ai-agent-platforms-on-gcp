-- Lab 8.5 — what does CostPilot itself cost? Query your own FOCUS table.
-- Works once (1) every CostPilot resource carries labels team=finops, service=<name>, env=<env>,
-- (2) the billing export is mapped into FOCUS (Phase 2, sql/04), and (3) AI spend from the
-- gateway is loaded too (Phase 4, spend_to_focus.py).
SELECT
  DATE_TRUNC(DATE(ChargePeriodStart), MONTH)                 AS month,
  JSON_VALUE(Tags, '$.service')                              AS service,
  JSON_VALUE(Tags, '$.env')                                  AS env,
  ServiceCategory,
  ROUND(SUM(EffectiveCost), 2)                               AS effective_cost
FROM finops.focus_costs
WHERE ChargePeriodStart >= TIMESTAMP(DATE_SUB(DATE_TRUNC(CURRENT_DATE(), MONTH), INTERVAL 3 MONTH))
  AND (x_TeamId = 'finops' OR JSON_VALUE(Tags, '$.team') = 'finops')
GROUP BY month, service, env, ServiceCategory
ORDER BY month, effective_cost DESC;
