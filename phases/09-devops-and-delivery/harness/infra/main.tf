# Track B (Harness): the Google identities the Harness delegate and CI build pods use.
# Add to infra/tofu/envs/dev/main.tf:
#
#   module "harness" {
#     source             = "../../../../harness/infra"
#     project_id         = var.project_id
#     attestor_key_id    = module.supply_chain.attestor_key_id
#   }
#
# Two GSAs, each reachable only from one Kubernetes service account (Workload
# Identity). No key files are created, exactly like the GitHub track's WIF setup.

variable "project_id" { type = string }
variable "attestor_key_id" {
  type        = string
  description = "The built-by-ci KMS crypto key (Binary Authorization attestations)"
}
variable "builder_ksa" {
  type    = string
  default = "harness-builds/harness-builder"
}

resource "google_service_account" "delegate" {
  project      = var.project_id
  account_id   = "harness-delegate"
  display_name = "Harness delegate: reads Artifact Registry"
}

resource "google_service_account" "builder" {
  project      = var.project_id
  account_id   = "harness-builder"
  display_name = "Harness CI build pods: push, scan, sign, attest"
}

resource "google_project_iam_member" "delegate" {
  for_each = toset(["roles/artifactregistry.reader"])
  project  = var.project_id
  role     = each.value
  member   = "serviceAccount:${google_service_account.delegate.email}"
}

resource "google_project_iam_member" "builder" {
  for_each = toset([
    "roles/artifactregistry.writer",
    "roles/containeranalysis.notes.attacher",
    "roles/containeranalysis.occurrences.editor",
    "roles/binaryauthorization.attestorsViewer",
  ])
  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.builder.email}"
}

resource "google_service_account_iam_member" "builder_workload_identity" {
  service_account_id = google_service_account.builder.name
  role               = "roles/iam.workloadIdentityUser"
  member             = "serviceAccount:${var.project_id}.svc.id.goog[${var.builder_ksa}]"
}

# cosign key: separate from the attestor key, so each key has one purpose.
resource "google_kms_key_ring" "harness" {
  project  = var.project_id
  name     = "costpilot-harness"
  location = "global"
}

resource "google_kms_crypto_key" "cosign" {
  name     = "cosign"
  key_ring = google_kms_key_ring.harness.id
  purpose  = "ASYMMETRIC_SIGN"
  version_template {
    algorithm = "EC_SIGN_P256_SHA256"
  }
}

resource "google_kms_crypto_key_iam_member" "builder_signs" {
  for_each      = { cosign = google_kms_crypto_key.cosign.id, attestor = var.attestor_key_id }
  crypto_key_id = each.value
  role          = "roles/cloudkms.signerVerifier"
  member        = "serviceAccount:${google_service_account.builder.email}"
}

output "cosign_key_uri" {
  description = "Pipeline variable cosign_key"
  value       = "gcpkms://${google_kms_crypto_key.cosign.id}"
}
output "delegate_gsa" { value = google_service_account.delegate.email }
output "builder_gsa" { value = google_service_account.builder.email }
