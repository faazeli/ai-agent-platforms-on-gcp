-- Phase 2 · Lab 2.3 (real-data track) — map the Cloud Billing *detailed* export
-- to FOCUS columns.
--
-- Prerequisite: Billing → Billing export → BigQuery export → "Detailed usage cost"
-- enabled into a dataset. Table names look like
--   `<project>.<dataset>.gcp_billing_export_resource_v1_<BILLING_ACCOUNT_ID>`
-- Data starts arriving within a day of enabling it; history is not backfilled.
--
-- Google Cloud also publishes a FOCUS-formatted view template over this export.
-- Writing the mapping yourself once is the fastest way to understand FOCUS;
-- compare your result with Google's view afterwards.
--
-- This is a learning-grade mapping, not a conformance-grade one:
--   * EffectiveCost here = cost + credits (credits are negative). Proper
--     commitment amortization needs the commitment columns of the export.
--   * ListCost uses cost_at_list where the export provides it.
-- Replace EXPORT_TABLE before running.

CREATE OR REPLACE VIEW finops.v_billing_export_as_focus AS
SELECT
  billing_account_id                                     AS BillingAccountId,
  project.id                                             AS SubAccountId,
  'Google Cloud'                                         AS ServiceProviderName,
  service.description                                    AS ServiceName,
  CASE
    WHEN service.description IN ('Compute Engine', 'Kubernetes Engine', 'Cloud Run', 'Cloud Functions') THEN 'Compute'
    WHEN service.description IN ('BigQuery', 'Dataflow', 'Pub/Sub') THEN 'Analytics'
    WHEN service.description IN ('Cloud Storage') THEN 'Storage'
    WHEN service.description IN ('Cloud SQL', 'Firestore', 'AlloyDB', 'Spanner') THEN 'Databases'
    WHEN service.description LIKE 'Vertex AI%' OR service.description LIKE 'Gemini%' THEN 'AI and Machine Learning'
    WHEN service.description LIKE '%Network%' OR service.description = 'Cloud DNS' THEN 'Networking'
    ELSE 'Other'
  END                                                    AS ServiceCategory,
  CASE cost_type
    WHEN 'regular'    THEN 'Usage'
    WHEN 'tax'        THEN 'Tax'
    WHEN 'adjustment' THEN 'Adjustment'
    ELSE 'Usage'
  END                                                    AS ChargeCategory,
  usage_start_time                                       AS ChargePeriodStart,
  usage_end_time                                         AS ChargePeriodEnd,
  TIMESTAMP(PARSE_DATE('%Y%m', invoice.month))           AS BillingPeriodStart,
  CAST(cost AS NUMERIC)                                  AS BilledCost,
  CAST(cost + IFNULL((SELECT SUM(c.amount) FROM UNNEST(credits) AS c), 0) AS NUMERIC) AS EffectiveCost,
  CAST(cost_at_list AS NUMERIC)                          AS ListCost,
  currency                                               AS BillingCurrency,
  location.region                                        AS RegionId,
  resource.global_name                                   AS ResourceId,
  JSON_OBJECT(ARRAY(SELECT l.key   FROM UNNEST(labels) AS l),
              ARRAY(SELECT l.value FROM UNNEST(labels) AS l)) AS Tags,
  (SELECT l.value FROM UNNEST(labels) AS l WHERE l.key = 'team' LIMIT 1) AS x_TeamId
FROM `EXPORT_TABLE`
WHERE DATE(_PARTITIONTIME) >= DATE_SUB(CURRENT_DATE(), INTERVAL 400 DAY);
