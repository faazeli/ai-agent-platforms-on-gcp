-- Phase 2 · Lab 2.2 — The FOCUS cost table.
-- Run with:  bq query --use_legacy_sql=false < sql/01_dataset_and_table.sql
-- (replace `finops` if you chose another dataset name; the scripts do this for you)

CREATE SCHEMA IF NOT EXISTS finops
OPTIONS (
  location = 'US',
  description = 'CostPilot FinOps warehouse (FOCUS-shaped)',
  labels = [('team', 'finops'), ('service', 'costpilot'), ('env', 'dev')]
);

-- Design notes
-- * PARTITION BY the column almost every query filters on (the charge day).
--   BigQuery then reads only the partitions in your WHERE clause.
-- * CLUSTER BY the columns you filter and group on next, most selective first.
--   Within each partition, rows are sorted by these, so filters skip blocks.
-- * require_partition_filter = TRUE makes a query without a date filter fail
--   instead of silently scanning (and billing for) the whole table.
-- * Custom, non-FOCUS columns start with x_ as the FOCUS spec requires.
-- * Column names follow FOCUS 1.x. Check them against the column library of the
--   FOCUS version you target: https://focus.finops.org/focus-specification/
CREATE TABLE IF NOT EXISTS finops.focus_costs (
  BillingAccountId     STRING    NOT NULL OPTIONS (description = 'FOCUS: billing account that pays the invoice'),
  SubAccountId         STRING             OPTIONS (description = 'FOCUS: GCP project id'),
  ServiceProviderName  STRING             OPTIONS (description = 'FOCUS: who provides the service'),
  ServiceName          STRING             OPTIONS (description = 'FOCUS: e.g. BigQuery, Cloud Run'),
  ServiceCategory      STRING             OPTIONS (description = 'FOCUS: e.g. Compute, Storage, AI and Machine Learning'),
  ChargeCategory       STRING    NOT NULL OPTIONS (description = 'FOCUS: Usage | Purchase | Tax | Credit | Adjustment'),
  ChargePeriodStart    TIMESTAMP NOT NULL OPTIONS (description = 'FOCUS: inclusive start of the charge period'),
  ChargePeriodEnd      TIMESTAMP NOT NULL OPTIONS (description = 'FOCUS: exclusive end of the charge period'),
  BillingPeriodStart   TIMESTAMP          OPTIONS (description = 'FOCUS: start of the invoice period'),
  BilledCost           NUMERIC            OPTIONS (description = 'FOCUS: what the invoice charges'),
  EffectiveCost        NUMERIC            OPTIONS (description = 'FOCUS: amortized cost after commitments and discounts'),
  ListCost             NUMERIC            OPTIONS (description = 'FOCUS: cost at public list prices'),
  BillingCurrency      STRING             OPTIONS (description = 'FOCUS: ISO 4217 currency code'),
  RegionId             STRING             OPTIONS (description = 'FOCUS: provider region id'),
  ResourceId           STRING             OPTIONS (description = 'FOCUS: provider resource identifier'),
  Tags                 JSON               OPTIONS (description = 'FOCUS: key/value labels'),
  x_TeamId             STRING             OPTIONS (description = 'Custom: owning team, derived from Tags at load time')
)
PARTITION BY DATE(ChargePeriodStart)
CLUSTER BY x_TeamId, ServiceName, SubAccountId
OPTIONS (
  require_partition_filter = TRUE,
  description = 'FOCUS cost and usage rows, one per resource per charge period',
  labels = [('team', 'finops'), ('service', 'costpilot'), ('env', 'dev')]
);
