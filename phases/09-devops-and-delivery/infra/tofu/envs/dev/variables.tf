variable "project_id" {
  type        = string
  description = "GCP project for the dev environment"
}

variable "region" {
  type    = string
  default = "us-central1"
}

variable "lock_audit_retention" {
  type        = bool
  default     = false
  description = "PERMANENT once applied. Keep false in labs."
}

variable "enable_binary_authorization" {
  type        = bool
  default     = false
  description = "Turn on after CI produces attestations (Lab 9.6), or nothing will deploy."
}
