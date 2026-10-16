# GKE Autopilot: Google manages nodes; you pay for pod requests. Workload Identity
# is always on in Autopilot. Private nodes, a release channel, and Binary
# Authorization enforcement complete the baseline.

variable "project_id" { type = string }
variable "region" { type = string }
variable "network_id" { type = string }
variable "subnet_id" { type = string }
variable "name" {
  type    = string
  default = "costpilot"
}
variable "deletion_protection" {
  type    = bool
  default = true # set false only for throwaway lab clusters
}

resource "google_container_cluster" "autopilot" {
  project             = var.project_id
  name                = var.name
  location            = var.region
  enable_autopilot    = true
  network             = var.network_id
  subnetwork          = var.subnet_id
  deletion_protection = var.deletion_protection

  ip_allocation_policy {
    cluster_secondary_range_name  = "pods"
    services_secondary_range_name = "services"
  }

  private_cluster_config {
    enable_private_nodes    = true
    enable_private_endpoint = false # keep a public control-plane endpoint, restricted below
    master_ipv4_cidr_block  = "172.16.0.0/28"
  }

  master_authorized_networks_config {
    cidr_blocks {
      cidr_block   = "0.0.0.0/0" # TIGHTEN THIS: your office/VPN range or CI runner range
      display_name = "lab-anywhere"
    }
  }

  release_channel {
    channel = "REGULAR"
  }

  binary_authorization {
    evaluation_mode = "PROJECT_SINGLETON_POLICY_ENFORCE" # only images the policy allows (Lab 9.6)
  }
}

output "cluster_name" { value = google_container_cluster.autopilot.name }
output "workload_pool" { value = "${var.project_id}.svc.id.goog" }
