# CostPilot dev environment: everything Phases 1-8 run on, as code.
#   tofu init -backend-config="bucket=$PROJECT-tofu-state"
#   tofu plan -var project_id=$PROJECT -out plan.out
#   tofu apply plan.out           # from CI only, after review (Lab 9.4)

locals {
  apis = [
    "container.googleapis.com", "bigquery.googleapis.com", "aiplatform.googleapis.com",
    "artifactregistry.googleapis.com", "modelarmor.googleapis.com", "cloudkms.googleapis.com",
    "binaryauthorization.googleapis.com", "containeranalysis.googleapis.com",
    "logging.googleapis.com", "cloudtrace.googleapis.com", "secretmanager.googleapis.com",
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.apis)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

module "network" {
  source     = "../../modules/network"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

module "gke" {
  source              = "../../modules/gke"
  project_id          = var.project_id
  region              = var.region
  network_id          = module.network.network_id
  subnet_id           = module.network.subnet_id
  deletion_protection = false # dev only: lets `tofu destroy` rebuild from scratch (Lab 9.2)
}

module "bigquery" {
  source     = "../../modules/bigquery"
  project_id = var.project_id
  depends_on = [google_project_service.apis]
}

module "iam" {
  source     = "../../modules/iam"
  project_id = var.project_id
  depends_on = [module.gke] # the workload identity pool exists once the cluster does
}

module "artifact_registry" {
  source     = "../../modules/artifact_registry"
  project_id = var.project_id
  region     = var.region
  depends_on = [google_project_service.apis]
}

module "audit" {
  source         = "../../modules/audit"
  project_id     = var.project_id
  lock_retention = var.lock_audit_retention
}

module "supply_chain" {
  count      = var.enable_binary_authorization ? 1 : 0
  source     = "../../modules/supply_chain"
  project_id = var.project_id
  depends_on = [google_project_service.apis]
}

output "cluster" { value = module.gke.cluster_name }
output "image_repository" { value = module.artifact_registry.repository }
output "workload_service_accounts" { value = module.iam.gsa_emails }
output "audit_bucket" { value = module.audit.bucket }
