# Terraform Global Configuration

This directory contains environment-specific Terraform variables and backend configurations.

## Files

- **`global_shell_vars.sh`** - Shell variables used by CI/CD workflows
- **`terraform.tfvars`** - Production configuration (main branch)
- **`dev.tfvars`** - Development configuration (develop branch)
- **`backend_config.hcl`** - Production Terraform state bucket
- **`backend_config_dev.hcl`** - Development Terraform state bucket

## Usage

### Local Development

```bash
# Development
cd terraform/
terraform init -backend-config=../terraform_global_config/backend_config_dev.hcl
terraform apply -var-file="../terraform_global_config/dev.tfvars"

# Production
cd terraform/
terraform init -backend-config=../terraform_global_config/backend_config.hcl
terraform apply -var-file="../terraform_global_config/terraform.tfvars"
```

### CI/CD

Workflows automatically load the correct configuration based on branch:
- `main` branch → `terraform.tfvars` (production)
- `develop` branch → `dev.tfvars` (development)

## Setup Instructions

1. **Copy example files:**
   ```bash
   cp global_shell_vars.sh.example global_shell_vars.sh
   cp terraform.tfvars.example terraform.tfvars
   cp dev.tfvars.example dev.tfvars
   ```

2. **Edit configuration files** with your project IDs and settings

3. **Create state buckets:**
   ```bash
   # Production
   gsutil mb -p your-prod-project-id -l europe-west4 gs://tf-state-your-prod-project-id
   gsutil versioning set on gs://tf-state-your-prod-project-id

   # Development
   gsutil mb -p your-dev-project-id -l europe-west4 gs://tf-state-your-dev-project-id
   gsutil versioning set on gs://tf-state-your-dev-project-id
   ```

## Environment Separation

Each environment (dev/prod) uses:
- ✅ Separate GCP project
- ✅ Separate Terraform state bucket
- ✅ Separate Firestore database
- ✅ Separate Cloud Run services
- ✅ Separate YouTube API quota
- ✅ Separate Gemini budget
