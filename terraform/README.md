# Global Terraform Infrastructure

This directory contains the **global/shared infrastructure** for all Copycat microservices.

## What Goes Here

### Core Infrastructure
- **APIs** (`api.tf`) - Enable all required GCP APIs
- **API Keys** (`api-keys.tf`) - YouTube Data API key (auto-generated & restricted)
- **Secret Manager** (`secrets.tf`) - Secrets for API keys and configuration
- **Artifact Registry** (`artifact_registry.tf`) - Docker & Python repositories
- **Firestore** (`firestore.tf`) - NoSQL database for video metadata
- **Cloud Storage** (`storage.tf`) - Buckets for frames and results
- **PubSub** (`pubsub.tf`) - Event-driven messaging topics
- **BigQuery** (`bigquery.tf`) - Analytics and results tables

### What Doesn't Go Here
- **Service-specific resources** → Goes in `services/{service}/terraform/`
  - Cloud Run services
  - Service-specific IAM bindings
  - PubSub subscriptions for the service

## Structure

```
terraform/
├── provider.tf              # GCP provider configuration
├── variables.tf             # Input variables
├── outputs.tf               # Outputs for services to consume
├── api.tf                   # Enable GCP APIs
├── api-keys.tf              # YouTube API key (auto-generated)
├── secrets.tf               # Secret Manager configuration
├── artifact_registry.tf     # Docker & Python repositories
├── firestore.tf             # Firestore database
├── storage.tf               # Cloud Storage buckets
├── pubsub.tf                # PubSub topics & dead letter
├── bigquery.tf              # BigQuery datasets & tables
└── README.md                # This file
```

**Why separate files?**
- ✅ Clear separation of concerns
- ✅ Easy to find and modify specific resources
- ✅ Better for code review
- ✅ Modular and maintainable

## Usage

### Quick Setup

```bash
# Use the setup script (recommended)
./scripts/setup-infra.sh
```

### Manual Setup

```bash
cd terraform

# Create terraform.tfvars
echo 'project_id = "your-project-id"' > terraform.tfvars
echo 'region = "us-central1"' >> terraform.tfvars

# Initialize Terraform
terraform init -backend-config="bucket=${PROJECT_ID}-terraform-state"

# Preview changes
terraform plan

# Apply infrastructure
terraform apply
```

### What Gets Created

**Automatically Generated:**
- ✅ YouTube API key (restricted to youtube.googleapis.com)
- ✅ YouTube API key stored in Secret Manager
- ✅ All infrastructure resources

**No Manual Steps:**
- 🎉 No need to manually create API keys
- 🎉 No need to manually add secrets
- 🎉 Everything is Infrastructure as Code!

### Outputs

Services reference these outputs via remote state:

```hcl
# In services/api-gateway/terraform/remote.tf
data "terraform_remote_state" "global" {
  backend = "gcs"
  config = {
    bucket = var.state_bucket
    prefix = "copycat/global-infra"
  }
}

# Use outputs
data.terraform_remote_state.global.outputs.artifact_registry_repo
data.terraform_remote_state.global.outputs.vpc_id
```

## Deployment Order

1. **First**: Deploy global infrastructure (this directory)
2. **Then**: Deploy services individually from `services/{service}/terraform/`

## Variables

Create a `terraform.tfvars` file (gitignored):

```hcl
project_id = "your-gcp-project-id"
region     = "europe-west4"  # or us-central1, etc.
```
