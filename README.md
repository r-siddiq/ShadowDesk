# ShadowDesk

Autonomous ML-Powered Trading Platform with Docker Compose local deployment.

## Overview

ShadowDesk is a system-agnostic autonomous trading platform that provides:
- Real-time stock signal generation via ML inference
- Automated trade execution
- Full ML pipeline (training, validation, deployment)
- Observability stack (metrics, logging, dashboards)
- Demo mode with paper trading (no real money)

## ⚠️ Security Notice

This is an **educational and portfolio demonstration** project.

### Local Development Credentials

The `docker-compose.yml` contains default development credentials for local services (MinIO, Vault, Grafana, Airflow, etc.):

- **Intentionally included** for local development only
- **Not production credentials** - for Docker Compose local stack only
- **Not connected to real trading** - uses Alpaca paper trading

### Production Secrets

Production secrets are managed via:
- **HashiCorp Vault** - Primary secrets management
- **Sealed Secrets** - GitOps-safe encrypted secrets for Kubernetes

**Never commit real API keys or production credentials.**

## Architecture

```
ShadowDesk/
├── docker-compose.yml     # Local deployment (dev credentials only)
├── config/               # Local configs (prometheus.yml, kind-config.yaml)
├── docker-config/         # Docker build configs
├── project/               # Source code
│   ├── cluster_b/
│   │   ├── api/         # FastAPI trading service
│   │   ├── train/       # ML training & Airflow DAGs
│   │   └── trading/     # Trading execution (Alpaca broker)
│   ├── dashboard-streamlit/  # Streamlit dashboard
│   ├── shared/          # MinIO, Vault, Qdrant helpers
│   └── tests/           # Test suite + local validation
├── k8s/                  # Kubernetes manifests + Helm charts
│   ├── argocd/          # ArgoCD AppProject & Applications
│   ├── helm/            # shadowdesk-infra, shadowdesk-compute
│   └── sealed-secrets/  # Encrypted secrets (safe to commit)
└── docs/                 # Documentation
```

## Local Quick Start

### Prerequisites
- Docker and Docker Compose
- 8GB+ RAM recommended

### Start the Stack
```bash
docker-compose up -d
docker-compose ps
docker-compose logs -f fastapi
```

### Seed Local Data
```bash
cd project
python tests/local_stack_bootstrap.py
```

### Service URLs
| Service | URL | Credentials |
|---------|-----|-------------|
| FastAPI | http://localhost:18000 | - |
| Streamlit | http://localhost:18501 | admin/shadowdesk |
| Airflow | http://localhost:18080 | admin / [generated at runtime] |
| MLflow | http://localhost:15000 | - |
| Prometheus | http://localhost:19090 | - |
| Grafana | http://localhost:13000 | admin/admin |
| Vault | http://localhost:18200 | dev token: shadowdesk-devtoken |
| Qdrant | http://localhost:16333 | - |
| MinIO Console | http://localhost:19001 | shadowdesk/shadowdesk123 |

Retrieve Airflow password:
```bash
docker compose exec -T airflow cat /opt/airflow/simple_auth_manager_passwords.json.generated
```

## Development

### Code Quality (Required for PRs)
```bash
ruff check .
black --check .
isort --check-only .
pytest tests/ -v
```

### Install Dev Tools
```bash
pip install ruff black isort pytest pytest-cov
```

### Run Tests
```bash
cd project
pytest tests/ -v
```

### Validate Local Stack
```bash
python tests/validate_local_stack.py --bootstrap  # Full validation
```

## API Endpoints

### Account
- `GET /account/` - Account info
- `GET /account/portfolio` - Portfolio summary
- `GET /account/history` - Trade history

### Trading
- `GET /trading/signals/{symbol}` - Get signal
- `POST /trading/signals/batch` - Batch signals
- `GET /trading/positions` - Current positions
- `POST /trading/orders` - Submit order
- `DELETE /trading/orders/{order_id}` - Cancel order
- `POST /trading/cycle` - Run full trading cycle

## Demo Mode

When no Alpaca API keys are configured, the system runs in **demo mode**:
- Mock $100,000 portfolio
- Simulated positions (AAPL, NVDA, MSFT)
- Heuristic signals when model unavailable

## CI/CD

GitOps pipeline: GitHub Actions → ArgoCD → Kubernetes

| Stage | Tools |
|-------|-------|
| Lint | ruff, black, isort |
| Test | pytest, pytest-cov |
| Deploy | ArgoCD CLI, Helm |

## License

Apache 2.0 - see [LICENSE](LICENSE)
