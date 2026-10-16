terraform {
  required_version = ">= 1.8"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 6.0, < 8.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
  # Every resource gets these labels, so its cost lands in FOCUS Tags (Phase 8, Lab 8.5).
  default_labels = {
    team    = "finops"
    service = "costpilot"
    env     = "dev"
  }
}
