-- Lab 6.3 — the third RBAC layer: BigQuery itself filters rows by team.
--
-- Even if a bug in cost-api forgot a team check, BigQuery would only return the
-- rows the *caller's identity* may see. Grant by Google group, never by person.
-- Replace example.com groups with yours. Note: once any row access policy exists
-- on a table, principals not covered by a policy see NO rows.

CREATE OR REPLACE ROW ACCESS POLICY payments_team
ON finops.focus_costs
GRANT TO ('group:payments-team@example.com')
FILTER USING (x_TeamId = 'payments');

CREATE OR REPLACE ROW ACCESS POLICY search_team
ON finops.focus_costs
GRANT TO ('group:search-team@example.com')
FILTER USING (x_TeamId = 'search');

-- FinOps admins and the cost-api workload see everything. cost-api enforces the
-- per-user team scope itself, because BigQuery sees cost-api's identity, not the
-- end user's. That is exactly why the API layer check matters.
CREATE OR REPLACE ROW ACCESS POLICY finops_all
ON finops.focus_costs
GRANT TO ('group:finops-admins@example.com',
          'serviceAccount:cost-api-gsa@PROJECT_ID.iam.gserviceaccount.com')
FILTER USING (TRUE);

-- Check what a policy does without switching users:
--   SELECT * FROM `region-us`.INFORMATION_SCHEMA.ROW_ACCESS_POLICIES;
