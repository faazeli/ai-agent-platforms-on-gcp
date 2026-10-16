# Phase 6's immutable audit trail as code: a log sink to a bucket with a retention
# policy. is_locked = true is PERMANENT; keep it false until you mean it.

variable "project_id" { type = string }
variable "location" {
  type    = string
  default = "US"
}
variable "retention_days" {
  type    = number
  default = 1
}
variable "lock_retention" {
  type    = bool
  default = false
}

resource "google_storage_bucket" "audit" {
  project                     = var.project_id
  name                        = "${var.project_id}-costpilot-audit"
  location                    = var.location
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"

  retention_policy {
    retention_period = var.retention_days * 86400
    is_locked        = var.lock_retention
  }
}

resource "google_logging_project_sink" "audit" {
  project                = var.project_id
  name                   = "costpilot-audit"
  destination            = "storage.googleapis.com/${google_storage_bucket.audit.name}"
  filter                 = "jsonPayload.event_type=\"audit\""
  unique_writer_identity = true
}

resource "google_storage_bucket_iam_member" "sink_writer" {
  bucket = google_storage_bucket.audit.name
  role   = "roles/storage.objectCreator"
  member = google_logging_project_sink.audit.writer_identity
}

output "bucket" { value = google_storage_bucket.audit.name }
