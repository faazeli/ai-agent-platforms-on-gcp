# Remote state in GCS: shared, locked, versioned. Create the bucket once by hand:
#   gcloud storage buckets create gs://$PROJECT-tofu-state --location=US --uniform-bucket-level-access
#   gcloud storage buckets update gs://$PROJECT-tofu-state --versioning
# then:  tofu init -backend-config="bucket=$PROJECT-tofu-state"
terraform {
  backend "gcs" {
    prefix = "costpilot/dev"
  }
}
