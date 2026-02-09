from fastapi.testclient import TestClient

from cluster_b.api.main import app


def test_metrics_endpoint_exports_api_http_requests_counter() -> None:
    client = TestClient(app)

    client.get("/health")
    response = client.get("/metrics")

    assert "api_http_requests_total" in response.text
