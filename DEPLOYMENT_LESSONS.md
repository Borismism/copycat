# Deployment Lessons Learned

## Critical Mistakes & Fixes

### 1. Terraform State Separation (CRITICAL)
**Mistake**: All services shared the same state file, causing state corruption and accidental destruction of global infrastructure.

**Fix**: Each terraform backend needs a unique prefix:
- Global: `prefix=copycat/global-infra`
- Services: `prefix=copycat/services/{service-name}`

Updated `deploy.sh` line 216-219:
```bash
terraform init \
    -backend-config="../../../$BACKEND_CONFIG" \
    -backend-config="prefix=copycat/services/${service}" \
    -reconfigure
```

### 2. Function Output Pollution
**Mistake**: `build_and_push_image()` logged to stdout, polluting the returned image URL variable. This caused Cloud Run to receive invalid empty image paths.

**Fix**: Redirect all logs to stderr with `>&2`:
```bash
log_info "Building..." >&2
docker build ... >&2
echo "$image_url"  # Only this goes to stdout
```

### 3. Backend Config Missing Prefix
**Mistake**: `backend_config_dev.hcl` only had bucket, missing the prefix. This caused global terraform state to be saved at bucket root instead of proper location.

**Fix**: Added to `terraform_global_config/backend_config_dev.hcl`:
```hcl
bucket = "irdeto-copycat-tf-state"
prefix = "copycat/global-infra"
```

### 4. Cloud Build vs Local Docker
**Issue**: Cloud Build adds complexity and cost. Local builds are faster for development.

**Fix**: Changed deploy.sh to use local Docker with `--platform linux/amd64` for Cloud Run compatibility.

### 5. State Bucket Name Mismatch
**Mistake**: Services' `data.tf` used `${var.project_id}-terraform-state` but actual bucket was `irdeto-copycat-tf-state`.

**Fix**: Hardcoded correct bucket name in all service `data.tf` files.

### 6. ADC Quota Project Missing
**Mistake**: Application Default Credentials needed quota project set for API Keys API.

**Fix**: `gcloud auth application-default set-quota-project irdeto-copycat-internal-dev`

### 7. Import Existing Resources
**Mistake**: Tried to create resources that already existed after state separation.

**Fix**: Import existing resources:
```bash
terraform import -var="image_name=..." google_service_account.name projects/.../serviceAccounts/...
```

## Correct Deployment Order
1. Deploy global infrastructure: `./deploy.sh infra dev`
2. Deploy services one by one: `./deploy.sh discovery-service dev`
3. Each service gets its own isolated state in GCS

## State File Locations
```
gs://irdeto-copycat-tf-state/
├── copycat/global-infra/default.tfstate
└── copycat/services/
    ├── discovery-service/default.tfstate
    ├── risk-analyzer-service/default.tfstate
    ├── vision-analyzer-service/default.tfstate
    ├── api-service/default.tfstate
    └── frontend-service/default.tfstate
```

## Key Takeaway
**ALWAYS** use unique state prefixes for each terraform root module. Shared state causes catastrophic failures.
