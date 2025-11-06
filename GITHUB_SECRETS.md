# GitHub Secrets Setup

## 🔑 Required Secrets

After deploying global infrastructure with `./deploy.sh infra dev` and `./deploy.sh infra prod`, you need to add these secrets to your GitHub repository.

### How to Add Secrets

1. Go to your GitHub repository
2. Click **Settings** → **Secrets and variables** → **Actions**
3. Click **New repository secret**
4. Add each secret below

---

## Secrets to Add

### 1. GCP_WORKLOAD_IDENTITY_PROVIDER

**Get the value:**
```bash
# After running ./deploy.sh infra dev or ./deploy.sh infra prod
cd terraform/
terraform output wif_provider
```

**Example value:**
```
projects/123456789/locations/global/workloadIdentityPools/github-pool/providers/github-provider-copycat
```

**Add to GitHub:**
- Name: `GCP_WORKLOAD_IDENTITY_PROVIDER`
- Value: (paste output from above)

---

### 2. GCP_SERVICE_ACCOUNT

**Get the value:**
```bash
# After running ./deploy.sh infra dev or ./deploy.sh infra prod
cd terraform/
terraform output wif_service_account
```

**Example value:**
```
github-actions-deployer@your-project-id.iam.gserviceaccount.com
```

**Add to GitHub:**
- Name: `GCP_SERVICE_ACCOUNT`
- Value: (paste output from above)

---

## ✅ That's It!

Only **2 secrets** needed:
- ✅ `GCP_WORKLOAD_IDENTITY_PROVIDER`
- ✅ `GCP_SERVICE_ACCOUNT`

### Why Only 2 Secrets?

**Workload Identity Federation (WIF)** eliminates the need for service account keys:
- ❌ No `GCP_PROJECT_ID` secret (loaded from tfvars)
- ❌ No `GCP_REGION` secret (loaded from tfvars)
- ❌ No service account JSON keys (insecure!)
- ❌ No API keys in GitHub (stored in Secret Manager)

### How It Works

1. **GitHub Actions** requests an OIDC token
2. **WIF** exchanges it for GCP credentials
3. **Service Account** has permissions to deploy
4. **Terraform** loads project-specific config from `terraform_global_config/`

---

## 🔒 Security Benefits

- ✅ No long-lived credentials in GitHub
- ✅ No service account JSON keys
- ✅ Automatic credential rotation
- ✅ Fine-grained permissions per service account
- ✅ Audit trail in GCP IAM

---

## 🧪 Test the Setup

After adding secrets, test with a manual workflow dispatch:

1. Go to **Actions** tab in GitHub
2. Select **Deploy Service** workflow
3. Click **Run workflow**
4. Select service: `discovery-service`
5. Select environment: `dev`
6. Click **Run workflow**

If successful, you'll see:
- ✅ Authentication via WIF
- ✅ Docker image build
- ✅ Terraform deployment
- ✅ Health check passed

---

## 🔄 Per-Environment Setup

### Option 1: Single Set of Secrets (Recommended)

Use **one** set of secrets that works for both dev and prod:
- The workflow automatically selects the right project based on branch
- `main` branch → uses `terraform.tfvars` (prod)
- `develop` branch → uses `dev.tfvars` (dev)

**Add to GitHub:**
- `GCP_WORKLOAD_IDENTITY_PROVIDER` (from prod deployment)
- `GCP_SERVICE_ACCOUNT` (from prod deployment)

### Option 2: Separate Secrets (Advanced)

If you want complete separation, use **GitHub Environments**:

**Settings → Environments → New environment**

Create two environments:
1. **dev** environment with dev secrets
2. **prod** environment with prod secrets

Then the workflow will use the right secrets based on environment.

---

## 📋 Quick Reference

```bash
# Deploy infrastructure first
./deploy.sh infra dev
./deploy.sh infra prod

# Get WIF provider
cd terraform/
terraform output wif_provider

# Get service account
terraform output wif_service_account

# Add both to GitHub → Settings → Secrets → Actions
```

**That's all you need!** 🎉
