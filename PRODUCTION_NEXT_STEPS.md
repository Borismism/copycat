# Production Setup - Next Steps

## 1. Configure DNS
Add A record: `copycat.borism.nl` → `136.110.144.167` (SSL will auto-provision in 15-30 min)

## 2. Add GitHub Secrets
Go to https://github.com/Borismism/copycat/settings/secrets/actions and add:
- `GCP_WORKLOAD_IDENTITY_PROVIDER`: `projects/297485357024/locations/global/workloadIdentityPools/copycat-pool/providers/github-provider-copycat`
- `GCP_SERVICE_ACCOUNT`: `copycat-github-deployer@copycat-429012.iam.gserviceaccount.com`

## 3. Deploy Services (after DNS)
`./deploy.sh all prod` or push to `main` branch for auto-deployment
