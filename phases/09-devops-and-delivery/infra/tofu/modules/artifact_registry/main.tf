# Docker images live here. Cleanup policies keep storage (and cost) bounded.

variable "project_id" { type = string }
variable "region" { type = string }

resource "google_artifact_registry_repository" "images" {
  project       = var.project_id
  location      = var.region
  repository_id = "costpilot"
  format        = "DOCKER"
  description   = "CostPilot container images"

  docker_config {
    immutable_tags = true # a tag can never be moved to a different image
  }

  cleanup_policies {
    id     = "keep-recent"
    action = "KEEP"
    most_recent_versions {
      keep_count = 20
    }
  }
  cleanup_policies {
    id     = "delete-old-untagged"
    action = "DELETE"
    condition {
      tag_state  = "UNTAGGED"
      older_than = "1209600s" # 14 days
    }
  }
}

output "repository" {
  value = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.images.repository_id}"
}
