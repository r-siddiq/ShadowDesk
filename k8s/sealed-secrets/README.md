# ShadowDesk Sealed Secrets

## Overview

This directory contains SealedSecret resources for ShadowDesk that are safe to commit to Git. Sealed Secrets can only be decrypted by the Sealed Secrets controller running in your cluster.

## IMPORTANT: Placeholder Values

The file `shadowdesk-secrets.yaml` contains **PLACEHOLDER VALUES** that will NOT work in production. These are unique per cluster and cannot be reused.

## How to Generate Real Sealed Secret Values

### Prerequisites

1. A running Kubernetes cluster with kind or similar
2. `kubeseal` CLI installed: https://github.com/bitnami-labs/sealed-secrets/releases
3. The Sealed Secrets controller installed in your cluster

### Generate Real Values

1. **First, deploy to your cluster to create the namespace and secrets:**

   ```bash
   # Run the bootstrap script
   ./k8s/bootstrap/setup-kind.sh

   # Or manually create the namespaces
   kubectl create namespace shadowdesk-storage
   kubectl create namespace shadowdesk-compute
   ```

2. **Create a source secrets file with your actual values:**

   Create `k8s/bootstrap/secrets-source.yaml` with:
   ```yaml
   # MinIO credentials
   minio-access-key: your-minio-access-key
   minio-secret-key: your-minio-secret-key

   # Vault token
   vault-token: your-vault-token

   # Grafana credentials
   admin-user: admin
   admin-password: your-grafana-password

   # Airflow credentials
   airflow-username: admin
   airflow-password: your-airflow-password

   # Alpaca API keys (for trading)
   alpaca-api-key: your-alpaca-api-key
   alpaca-secret-key: your-alpaca-secret-key

   # Streamlit dashboard password
   dashboard-password: your-dashboard-password
   ```

3. **Run the seal script:**

   ```bash
   cd k8s/bootstrap
   ./seal-secrets.sh
   ```

   This will generate `k8s/sealed-secrets/shadowdesk-secrets.yaml` with real sealed values.

4. **Commit the sealed secrets file:**

   ```bash
   git add k8s/sealed-secrets/shadowdesk-secrets.yaml
   git commit -m "Add sealed secrets for production"
   git push
   ```

## Secrets That Need to Be Sealed

| Secret Name | Namespace | Keys |
|-------------|-----------|------|
| `shadowdesk-minio-secret` | shadowdesk-storage | `minio-access-key`, `minio-secret-key` |
| `shadowdesk-vault-secret` | shadowdesk-storage | `vault-token` |
| `shadowdesk-grafana-secret` | shadowdesk-storage | `admin-user`, `admin-password` |
| `shadowdesk-airflow-secret` | shadowdesk-compute | `airflow-username`, `airflow-password` |
| `shadowdesk-alpaca-secret` | shadowdesk-compute | `alpaca-api-key`, `alpaca-secret-key` |
| `shadowdesk-streamlit-secret` | shadowdesk-compute | `dashboard-password` |

## Current Status

| Secret | Status | Notes |
|--------|--------|-------|
| shadowdesk-minio-secret | PLACEHOLDER | Must run seal-secrets.sh |
| shadowdesk-vault-secret | PLACEHOLDER | Must run seal-secrets.sh |
| shadowdesk-grafana-secret | PLACEHOLDER | Must run seal-secrets.sh |
| shadowdesk-airflow-secret | PLACEHOLDER | Must run seal-secrets.sh |
| shadowdesk-alpaca-secret | PLACEHOLDER | Must run seal-secrets.sh |
| shadowdesk-streamlit-secret | MISSING | Added but not yet sealed |

## Security Notes

- Never commit real secrets to Git without sealing them
- Sealed Secrets are NOT encrypted - they are just obscured. The Sealed Secrets controller in your cluster is what provides the actual security
- In production, consider using a proper secrets manager like HashiCorp Vault with the Vault provider for external secrets
