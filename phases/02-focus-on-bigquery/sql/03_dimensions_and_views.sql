-- Phase 2 · Lab 2.5 — Dimensions and a materialized view for dashboards.

-- A small team dimension: who owns the spend, and which cost center pays.
CREATE OR REPLACE TABLE finops.dim_team (
  team_id      STRING NOT NULL,
  display_name STRING,
  owner_email  STRING,
  cost_center  STRING
);

INSERT INTO finops.dim_team (team_id, display_name, owner_email, cost_center) VALUES
  ('payments',      'Payments',       'payments-lead@example.com', 'CC-1001'),
  ('search',        'Search',         'search-lead@example.com',   'CC-1002'),
  ('data-platform', 'Data Platform',  'data-lead@example.com',     'CC-2001'),
  ('ml-research',   'ML Research',    'ml-lead@example.com',       'CC-3001');

-- A service dimension mapping provider service names to internal groupings.
CREATE OR REPLACE TABLE finops.dim_service (
  service_name     STRING NOT NULL,
  service_category STRING,
  internal_group   STRING
);

INSERT INTO finops.dim_service (service_name, service_category, internal_group) VALUES
  ('Compute Engine',    'Compute',                 'infrastructure'),
  ('Kubernetes Engine', 'Compute',                 'infrastructure'),
  ('Cloud Run',         'Compute',                 'infrastructure'),
  ('BigQuery',          'Analytics',               'data'),
  ('Cloud Storage',     'Storage',                 'data'),
  ('Vertex AI',         'AI and Machine Learning', 'ai');

-- Pre-aggregated daily cost per team and service. BigQuery keeps it fresh
-- incrementally and can rewrite matching queries on the base table to use it.
CREATE MATERIALIZED VIEW IF NOT EXISTS finops.mv_daily_team_cost
PARTITION BY day
CLUSTER BY x_TeamId, ServiceName
OPTIONS (enable_refresh = TRUE, refresh_interval_minutes = 60)
AS
SELECT
  DATE(ChargePeriodStart) AS day,
  x_TeamId,
  ServiceName,
  SUM(EffectiveCost) AS effective_cost,
  SUM(BilledCost)    AS billed_cost
FROM finops.focus_costs
WHERE ChargePeriodStart >= TIMESTAMP('2000-01-01')
GROUP BY day, x_TeamId, ServiceName;
