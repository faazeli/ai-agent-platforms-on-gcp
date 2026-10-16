# Phase 2 — FOCUS cost data on BigQuery

| Time | Cloud cost | Builds on | You produce |
| --- | --- | --- | --- |
| Weeks 4–6 (≈ 25 h) | ≈ $0 (stays inside BigQuery's free tier) | Phase 1 `cost-api` | A partitioned, clustered FOCUS table; analyst queries; a BigQuery-backed `cost-api` |

## Why this phase matters

Agents are only as good as the data they query. FinOps data has two hard problems: every vendor names things differently, and the tables get huge. FOCUS (the FinOps Open Cost and Usage Specification) solves the first with a shared schema. Partitioning and clustering solve the second. You will feel both: by the end of this phase, the same question costs a fraction of the bytes on your well-designed table.

FOCUS 1.4, ratified June 4, 2026, is the current version at the time of writing; it added invoice-reconciliation datasets and richer commitment columns ([FOCUS specification](https://focus.finops.org/focus-specification/)). This course uses a core subset of columns that has been stable across 1.x.

## You will learn

- The FOCUS vocabulary, especially the difference between `BilledCost`, `EffectiveCost` and `ListCost`
- BigQuery table design: partitioning, clustering, `require_partition_filter`, `JSON` columns, `NUMERIC` for money
- Idempotent loading with a staging table and `MERGE`
- OLAP patterns: dimension tables, window functions, materialized views
- Cost guardrails: dry runs, `maximum_bytes_billed`, query labels
- Swapping an implementation behind an interface (Phase 1's `CostRepository`)

## Before you start

1. Phase 1 done (or start from `starter/cost-api`, which already contains the Phase 1 solution).
2. A GCP project with billing enabled, the `bq` CLI, and Application Default Credentials: see [SETUP.md](../../SETUP.md).
3. Read (about 2 hours):
   - [FOCUS specification](https://focus.finops.org/focus-specification/) overview, then skim the column library
   - BigQuery: [Partitioned tables](https://cloud.google.com/bigquery/docs/partitioned-tables), [Clustered tables](https://cloud.google.com/bigquery/docs/clustered-tables), [Parameterized queries](https://cloud.google.com/bigquery/docs/parameterized-queries)
   - [BigQuery pricing](https://cloud.google.com/bigquery/pricing): note the free tier for storage and on-demand queries, and check its current limits

```bash
export PROJECT=your-project-id
gcloud config set project "$PROJECT"
gcloud services enable bigquery.googleapis.com
gcloud auth application-default login
```

## What's in this folder

```
sql/01_dataset_and_table.sql      DDL for the dataset and the FOCUS table
sql/02_load_merge.sql             staging → FOCUS MERGE (idempotent)
sql/03_dimensions_and_views.sql   dim_team, dim_service, a materialized view
sql/04_billing_export_to_focus.sql  real-data track: billing export → FOCUS view
sql/queries/q01…q06               analyst queries (month-to-date, top resources, …)
scripts/load_sample.sh            create + load + merge in one go
scripts/dry_run_compare.sh        partitioned vs flat bytes scanned
starter/cost-api                  Phase 1 solution + a BigQuery repository to finish
solution/cost-api                 reference answer
tests/                            offline guardrail checks for the SQL and data
```

## Labs

### Lab 2.1 — Learn the vocabulary

In your own repo, create `docs/focus-glossary.md` and write one sentence, in your own words, for each column in the DDL (`sql/01_dataset_and_table.sql`). Then answer:

1. A team bought a one-year commitment in January. Which column shows the January invoice line? Which column shows that cost spread across the year?
2. Why should a team dashboard show `EffectiveCost` and the finance reconciliation use `BilledCost`?
3. Which column would you use to show savings versus public prices?

<details>
<summary>Check your answers</summary>

1. `BilledCost` on the `Purchase` row carries the invoice line. `EffectiveCost` on the covered `Usage` rows carries the amortized cost.
2. Teams should see the cost of what they used, smoothed over the commitment term. Finance needs what was actually invoiced, in the period it was invoiced.
3. `ListCost − EffectiveCost`.

</details>

### Lab 2.2 — Design the table

Read `sql/01_dataset_and_table.sql` slowly; the comments explain every choice. Then write down, before running anything:

- Which column did we partition on, and what query pattern justifies it?
- Why is `x_TeamId` the first clustering column rather than `ServiceName`?
- What does `require_partition_filter = TRUE` protect against, in dollars?

### Lab 2.3 — Load data

**Synthetic track (everyone):**

```bash
cd phases/02-focus-on-bigquery
PROJECT=$PROJECT ./scripts/load_sample.sh
```

The script generates 92 days of data ending yesterday, loads it into a staging table, and `MERGE`s it into `focus_costs`. Run it twice and confirm the row count doesn't change: that is idempotency, and it is what makes retries and backfills safe.

**Real-data track (optional, if your billing account has spend):** enable [Cloud Billing detailed export to BigQuery](https://cloud.google.com/billing/docs/how-to/export-data-bigquery-setup), wait a day for data, then adapt `sql/04_billing_export_to_focus.sql` (replace `EXPORT_TABLE`). Compare its output with the FOCUS view template Google publishes for the billing export.

**Check:** `bq query --use_legacy_sql=false "SELECT COUNT(*) FROM finops.focus_costs WHERE ChargePeriodStart >= TIMESTAMP('2000-01-01')"` returns about 2,760 rows.

### Lab 2.4 — Prove the design pays off

```bash
PROJECT=$PROJECT ./scripts/dry_run_compare.sh
```

The script builds an unpartitioned copy and dry-runs the same one-week, one-team query on both. Record both byte counts in your ADR. Then remove the date filter from the query and run it against `focus_costs`: it must fail. That failure is a feature.

> On a 3,000-row table the absolute numbers are tiny. The ratio is what scales: the same design on a 5 TB billing table is the difference between pennies and real money per query.

### Lab 2.5 — Analyst queries and OLAP patterns

Run each query in `sql/queries/` and read its result:

| Query | Question it answers |
| --- | --- |
| `q01_month_to_date_by_team` | What has each team spent this month, by service? |
| `q02_top_resources` | Which 10 resources cost a team the most? (parameterized) |
| `q03_day_over_day` | Which teams' spend changed most day to day? |
| `q04_untagged_share` | How much spend has no owner? |
| `q05_commitment_utilization` | Are we using what we committed to? |
| `q06_anomalies_moving_average` | Which days broke from the trailing 7-day pattern? |

```bash
bq query --use_legacy_sql=false --parameter=team_id:STRING:payments \
  --parameter=month:DATE:$(date -u +%Y-%m-01) < sql/queries/q02_top_resources.sql
```

You should find the planted findings: about 88% commitment utilization for payments (q05), untagged Cloud Storage spend in data-platform (q04), and an ml-research Vertex AI spike (q06).

Then write two queries of your own and add them to the folder, for example "cost per team per `ServiceCategory` this quarter" and "the 5 fastest-growing resources week over week". Run `pytest -q tests` from this folder: it checks that every query filters on the partition column and never hardcodes a team.

### Lab 2.6 — Put BigQuery behind `cost-api`

Open `starter/cost-api/src/cost_api/bigquery_repository.py`. The plumbing is done: `_query` runs a parameterized job with a bytes-billed ceiling in a worker thread, and `list_teams` reads `dim_team`. Implement the four methods marked `TODO Lab 2.6` so they match `InMemoryCostRepository` exactly, but aggregate in SQL.

```bash
cd starter/cost-api
pip install -e ".[dev,bigquery]"
pytest -q                                 # offline tests use a fake client
COST_API_DATA_SOURCE=bigquery COST_API_GCP_PROJECT=$PROJECT \
  uvicorn cost_api.main:app --app-dir src --reload
curl -s "localhost:8000/v1/teams/payments/summary?month=$(date -u +%Y-%m)" | python -m json.tool
```

Nothing in `main.py` changed. That is the payoff of the Phase 1 interface.

Finally, open BigQuery's job history in the console and find your API's queries by the label `service:cost-api`. Labels on jobs flow into your billing data, which is how CostPilot will eventually report its own cost (Phase 8).

## Done when

- [ ] `focus_costs` exists, partitioned by day and clustered, with `require_partition_filter`
- [ ] Your ADR records bytes scanned with and without partitioning
- [ ] You can explain each planted finding (commitment utilization, untagged spend, anomaly) from query output
- [ ] `cost-api` serves the same endpoints from BigQuery, and `pytest -q` passes in your starter
- [ ] `pytest -q tests` passes for this folder, including your two new queries

## Write it down (ADR)

`docs/adr/0002-cost-warehouse-design.md`: partition and cluster keys, the bytes comparison from Lab 2.4, the `maximum_bytes_billed` value you chose and why, and the conditions under which you'd add a materialized view.

## Teach it (5 minutes)

Show the dry-run comparison to someone who writes SQL against large tables. Ask what their biggest table is partitioned on. This is the conversation that later becomes your influence exercise in Phase 10.

## Stretch goals

- Add FOCUS commitment columns (`CommitmentDiscountId`, `CommitmentDiscountStatus`) to the generator and DDL, and rewrite q05 to use them.
- Load a second "provider" (for example a SaaS invoice CSV) into the same table and query across both: the point of FOCUS.
- Run a q06-style anomaly query on a schedule with BigQuery scheduled queries, writing to an `anomalies` table.

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| `Cannot query over table ... without a filter over column(s) 'ChargePeriodStart'` | Working as designed. Add a `ChargePeriodStart >= ...` condition. |
| `Query exceeded limit for bytes billed` | Your `maximum_bytes_billed` guardrail fired. Narrow the query or raise `COST_API_BQ_MAX_BYTES_BILLED` deliberately. |
| `google.auth.exceptions.DefaultCredentialsError` | Run `gcloud auth application-default login`. |
| q01 or q03 return no rows | They look at the current month/last two weeks. Re-run `load_sample.sh`, which always generates data ending yesterday. |
| `Access Denied: ... bigquery.jobs.create` | Grant yourself `roles/bigquery.user` and `roles/bigquery.dataEditor` on the project. |

## Teardown

Keep the dataset: Phases 3–9 use it. When you finish the course: `bq rm -r -f -d $PROJECT:finops`. Remove the flat copy from Lab 2.4 now: `bq rm -f -t $PROJECT:finops.focus_costs_flat`.
