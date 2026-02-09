"""Seed the local ShadowDesk stack with the state expected by the validator."""

import json
import sys
import time
from io import BytesIO
from pathlib import Path
from typing import Dict, List, Optional

import requests
from minio import Minio
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, PointStruct, VectorParams

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[2]
VAULT_URL = "http://localhost:18200"
MINIO_URL = "localhost:19000"
QDRANT_URL = "localhost"
QDRANT_PORT = 16333
GRAFANA_URL = "http://localhost:13000"
GRAFANA_DASHBOARD = REPO_ROOT / "config" / "grafana" / "dashboards" / "shadowalpha_overview.json"

DEFAULT_WATCHLIST = [
    "AAPL",
    "GOOGL",
    "MSFT",
    "AMZN",
    "TSLA",
    "NVDA",
    "META",
    "NFLX",
    "AMD",
    "INTC",
    "BA",
    "JPM",
    "V",
    "MA",
    "PYPL",
    "DIS",
    "KO",
    "PEP",
    "WMT",
    "COST",
    "NKE",
    "SBUX",
    "CRM",
    "ADBE",
    "ORCL",
]


def _wait_for_http(session: requests.Session, url: str, expected_status: int = 200, timeout_seconds: int = 60) -> None:
    """Wait until an HTTP endpoint responds with the expected status."""
    deadline = time.perf_counter() + timeout_seconds
    last_error = "service did not respond"

    while time.perf_counter() < deadline:
        try:
            response = session.get(url, timeout=10)
            if response.status_code == expected_status:
                return
            last_error = f"{url} returned {response.status_code}"
        except requests.RequestException as exc:
            last_error = str(exc)
        time.sleep(2)

    raise RuntimeError(last_error)


def _seed_vault(session: requests.Session) -> str:
    """Write the default local secrets into Vault."""
    _wait_for_http(session, f"{VAULT_URL}/v1/sys/health")
    headers = {"X-Vault-Token": "shadowdesk-devtoken"}
    payloads: Dict[str, Dict[str, object]] = {
        "trading": {
            "max_positions": 10,
            "position_size_pct": 0.02,
            "stop_loss_pct": 0.15,
            "max_total_risk": 0.25,
            "min_confidence": 0.60,
            "watchlist": DEFAULT_WATCHLIST,
        },
        "alpaca": {
            "api_key": "",
            "secret_key": "",
        },
        "dashboard": {
            "password": "shadowdesk",
        },
    }

    for path, payload in payloads.items():
        response = session.post(
            f"{VAULT_URL}/v1/secret/data/{path}",
            headers=headers,
            json={"data": payload},
            timeout=30,
        )
        response.raise_for_status()

    return "Vault secrets seeded"


def _put_json_object(client: Minio, bucket_name: str, object_name: str, payload: Dict[str, object]) -> None:
    """Upload a small JSON document into a MinIO bucket."""
    data = json.dumps(payload, indent=2).encode("utf-8")
    client.put_object(
        bucket_name,
        object_name,
        data=BytesIO(data),
        length=len(data),
        content_type="application/json",
    )


def _seed_minio() -> str:
    """Create the local MinIO buckets expected by the app and validator."""
    client = Minio(MINIO_URL, access_key="shadowdesk", secret_key="shadowdesk123", secure=False)
    buckets = {
        "stock-data": {
            "bootstrap/raw/seed.json": {"symbols": ["AAPL", "MSFT"], "source": "local-bootstrap"},
        },
        "shadowdesk-data": {
            "bootstrap/seed.json": {"status": "ready", "bucket": "shadowdesk-data"},
        },
        "shadowdesk-models": {
            "bootstrap/model.json": {"model": "validation-placeholder", "version": 1},
        },
    }

    for bucket_name, objects in buckets.items():
        if not client.bucket_exists(bucket_name):
            client.make_bucket(bucket_name)
        for object_name, payload in objects.items():
            _put_json_object(client, bucket_name, object_name, payload)

    return "MinIO buckets seeded"


def _seed_qdrant() -> str:
    """Create the default collection and seed one example point."""
    client = QdrantClient(host=QDRANT_URL, port=QDRANT_PORT, check_compatibility=False)
    collections = {collection.name for collection in client.get_collections().collections}
    if "stock_embeddings" not in collections:
        client.create_collection(
            collection_name="stock_embeddings",
            vectors_config=VectorParams(size=384, distance=Distance.COSINE),
        )

    vector = [0.01] * 384
    client.upsert(
        collection_name="stock_embeddings",
        points=[
            PointStruct(
                id=1,
                vector=vector,
                payload={"text": "ShadowDesk validation seed", "stock": "AAPL"},
            )
        ],
    )
    return "Qdrant collection seeded"


def _seed_grafana(session: requests.Session) -> str:
    """Create the Prometheus data source and import the local dashboard."""
    _wait_for_http(session, f"{GRAFANA_URL}/api/health")
    auth = ("admin", "admin")

    datasource = {
        "name": "Prometheus",
        "type": "prometheus",
        "access": "proxy",
        "url": "http://prometheus:9090",
        "isDefault": True,
        "basicAuth": False,
    }

    existing_datasource = session.get(
        f"{GRAFANA_URL}/api/datasources/name/Prometheus",
        auth=auth,
        timeout=30,
    )
    if existing_datasource.status_code == 404:
        response = session.post(
            f"{GRAFANA_URL}/api/datasources",
            auth=auth,
            json=datasource,
            timeout=30,
        )
        response.raise_for_status()
    else:
        existing_datasource.raise_for_status()

    dashboard_payload = json.loads(GRAFANA_DASHBOARD.read_text(encoding="utf-8"))
    response = session.post(
        f"{GRAFANA_URL}/api/dashboards/db",
        auth=auth,
        json={"dashboard": dashboard_payload, "folderId": 0, "overwrite": True},
        timeout=30,
    )
    response.raise_for_status()

    return "Grafana datasource and dashboard provisioned"


def bootstrap_local_stack(session: Optional[requests.Session] = None) -> List[str]:
    """Seed the local stack and return a list of completed steps."""
    managed_session = session or requests.Session()
    steps = [
        _seed_vault(managed_session),
        _seed_minio(),
        _seed_qdrant(),
        _seed_grafana(managed_session),
    ]
    return steps


def main() -> int:
    """Run the local bootstrap sequence from the command line."""
    session = requests.Session()
    try:
        steps = bootstrap_local_stack(session=session)
    except Exception as exc:
        print(f"Local bootstrap failed: {exc}", file=sys.stderr)
        return 1

    print("Local stack bootstrap complete:")
    for step in steps:
        print(f"  - {step}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
