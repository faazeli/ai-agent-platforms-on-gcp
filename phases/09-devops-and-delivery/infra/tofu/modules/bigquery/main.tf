# The FOCUS warehouse from Phase 2, as code. Same partitioning, clustering and
# partition-filter guard as sql/01_dataset_and_table.sql.

variable "project_id" { type = string }
variable "location" {
  type    = string
  default = "US"
}
variable "dataset_id" {
  type    = string
  default = "finops"
}

resource "google_bigquery_dataset" "finops" {
  project       = var.project_id
  dataset_id    = var.dataset_id
  location      = var.location
  description   = "CostPilot FinOps warehouse (FOCUS-shaped)"
  friendly_name = "finops"
}

resource "google_bigquery_table" "focus_costs" {
  project             = var.project_id
  dataset_id          = google_bigquery_dataset.finops.dataset_id
  table_id            = "focus_costs"
  description         = "FOCUS cost and usage rows"
  deletion_protection = true

  time_partitioning {
    type  = "DAY"
    field = "ChargePeriodStart"
  }
  require_partition_filter = true
  clustering               = ["x_TeamId", "ServiceName", "SubAccountId"]
  schema                   = file("${path.module}/focus_costs.schema.json")
}

output "dataset_id" { value = google_bigquery_dataset.finops.dataset_id }
output "table_id" { value = google_bigquery_table.focus_costs.table_id }
