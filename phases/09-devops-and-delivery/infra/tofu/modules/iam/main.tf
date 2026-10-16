# One Google service account per workload, least privilege, bound to its Kubernetes
# service account through Workload Identity. No keys are ever created (Phase 6).

variable "project_id" { type = string }
variable "namespace" {
  type    = string
  default = "costpilot"
}
variable "workloads" {
  description = "KSA name => project roles for its GSA"
  type        = map(list(string))
  default = {
    "cost-api"    = ["roles/bigquery.dataViewer", "roles/bigquery.jobUser"]
    "mcp-finops"  = []
    "agents"      = ["roles/modelarmor.user", "roles/cloudtrace.agent"]
    "litellm"     = ["roles/aiplatform.user"]
    "ledger-java" = []
  }
}

locals {
  bindings = flatten([
    for ksa, roles in var.workloads : [for role in roles : { ksa = ksa, role = role }]
  ])
}

resource "google_service_account" "workload" {
  for_each     = var.workloads
  project      = var.project_id
  account_id   = "${each.key}-gsa"
  display_name = "CostPilot ${each.key}"
}

resource "google_project_iam_member" "roles" {
  for_each = { for b in local.bindings : "${b.ksa}/${b.role}" => b }
  project  = var.project_id
  role     = each.value.role
  member   = "serviceAccount:${google_service_account.workload[each.value.ksa].email}"
}

resource "google_service_account_iam_member" "workload_identity" {
  for_each           = var.workloads
  service_account_id = google_service_account.workload[each.key].name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.namespace}/${each.key}]"
}

output "gsa_emails" {
  value = { for k, sa in google_service_account.workload : k => sa.email }
}
