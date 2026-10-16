# Lab 9.6 — only images our pipeline built and attested may run on the cluster.
#
# CI signs an attestation for each image digest with a Cloud KMS key; the Binary
# Authorization policy requires that attestation for everything except Google's
# system images. Unattested images are rejected at admission.

variable "project_id" { type = string }
variable "location" {
  type    = string
  default = "global"
}

resource "google_kms_key_ring" "binauthz" {
  project  = var.project_id
  name     = "costpilot-binauthz"
  location = var.location
}

resource "google_kms_crypto_key" "attestor" {
  name     = "built-by-ci"
  key_ring = google_kms_key_ring.binauthz.id
  purpose  = "ASYMMETRIC_SIGN"
  version_template {
    algorithm = "EC_SIGN_P256_SHA256"
  }
}

data "google_kms_crypto_key_version" "attestor" {
  crypto_key = google_kms_crypto_key.attestor.id
}

resource "google_container_analysis_note" "built_by_ci" {
  project = var.project_id
  name    = "built-by-ci"
  attestation_authority {
    hint {
      human_readable_name = "Built and tested by CostPilot CI"
    }
  }
}

resource "google_binary_authorization_attestor" "built_by_ci" {
  project = var.project_id
  name    = "built-by-ci"
  attestation_authority_note {
    note_reference = google_container_analysis_note.built_by_ci.name
    public_keys {
      id = data.google_kms_crypto_key_version.attestor.id
      pkix_public_key {
        public_key_pem      = data.google_kms_crypto_key_version.attestor.public_key[0].pem
        signature_algorithm = data.google_kms_crypto_key_version.attestor.public_key[0].algorithm
      }
    }
  }
}

resource "google_binary_authorization_policy" "policy" {
  project                       = var.project_id
  global_policy_evaluation_mode = "ENABLE" # allow Google-maintained system images

  # Third-party images we run without rebuilding. Better practice: mirror them into
  # Artifact Registry, scan them, and attest them in CI like our own images.
  admission_whitelist_patterns {
    name_pattern = "ghcr.io/berriai/litellm*"
  }
  admission_whitelist_patterns {
    name_pattern = "quay.io/argoproj/*"
  }

  default_admission_rule {
    evaluation_mode         = "REQUIRE_ATTESTATION"
    enforcement_mode        = "ENFORCED_BLOCK_AND_AUDIT_LOG"
    require_attestations_by = [google_binary_authorization_attestor.built_by_ci.name]
  }
}

output "attestor" { value = google_binary_authorization_attestor.built_by_ci.name }
output "kms_key_version" { value = data.google_kms_crypto_key_version.attestor.id }
