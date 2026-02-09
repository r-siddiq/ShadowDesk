"""
Sequential local-stack validation harness for ShadowDesk.

Run from the project directory:
    python tests/validate_local_stack.py
"""

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Tuple

import requests

try:
    from tests.local_stack_bootstrap import bootstrap_local_stack
except ImportError:
    from local_stack_bootstrap import bootstrap_local_stack

try:
    from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright
except ImportError:  # pragma: no cover - runtime dependency
    Browser = object  # type: ignore[assignment]
    BrowserContext = object  # type: ignore[assignment]
    Page = object  # type: ignore[assignment]
    sync_playwright = None

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS_ROOT = Path(__file__).resolve().parent / "artifacts" / "local_stack"

STREAMLIT_URL = "http://localhost:18501"
FASTAPI_URL = "http://localhost:18000"
MLFLOW_URL = "http://localhost:15000"
PROMETHEUS_URL = "http://localhost:19090"
GRAFANA_URL = "http://localhost:13000"
AIRFLOW_URL = "http://localhost:18080"
VAULT_URL = "http://localhost:18200"
MINIO_CONSOLE_URL = "http://localhost:19001"
MINIO_API_URL = "http://localhost:19000"
QDRANT_URL = "http://localhost:16333"


@dataclass
class ValidationResult:
    """Result for a single validation track."""

    name: str
    status: str = "PASS"
    validated: List[str] = field(default_factory=list)
    issues: List[str] = field(default_factory=list)
    duration_seconds: float = 0.0

    def add_validation(self, message: str) -> None:
        self.validated.append(message)

    def add_issue(self, message: str, fatal: bool = False) -> None:
        self.issues.append(message)
        if fatal:
            self.status = "FAIL"


def _make_request(
    session: requests.Session,
    method: str,
    url: str,
    expected_status: Optional[Sequence[int]] = None,
    **kwargs,
) -> requests.Response:
    response = session.request(method=method, url=url, timeout=30, **kwargs)
    if expected_status and response.status_code not in expected_status:
        raise RuntimeError(f"{method} {url} returned {response.status_code}: {response.text[:300]}")
    return response


def _save_failure_screenshot(page: Page, track: str, name: str) -> str:
    track_dir = ARTIFACTS_ROOT / track
    track_dir.mkdir(parents=True, exist_ok=True)
    target = track_dir / f"{name}.png"
    page.screenshot(path=str(target), full_page=True)
    return str(target)


def _wait_for_metric_series(session: requests.Session, query: str, timeout_seconds: int = 30) -> int:
    """Poll Prometheus until a query returns series or the timeout elapses."""
    deadline = time.perf_counter() + timeout_seconds
    last_count = 0

    while time.perf_counter() < deadline:
        payload = _make_request(
            session,
            "GET",
            f"{PROMETHEUS_URL}/api/v1/query",
            expected_status=[200],
            params={"query": query},
        ).json()
        last_count = len(payload.get("data", {}).get("result", []))
        if last_count:
            return last_count
        time.sleep(2)

    return last_count


def _attach_console_watch(
    page: Page,
    result: ValidationResult,
    ignored_console_patterns: Optional[Sequence[str]] = None,
) -> None:
    ignored_patterns = tuple(ignored_console_patterns or [])

    def handle_console(message) -> None:
        if message.type == "error":
            if ignored_patterns and any(pattern in message.text for pattern in ignored_patterns):
                return
            result.add_issue(f"Console error: {message.text}")

    def handle_page_error(exc: Exception) -> None:
        result.add_issue(f"Page error: {exc}")

    page.on("console", handle_console)
    page.on("pageerror", handle_page_error)


def _get_airflow_password() -> Optional[str]:
    command = [
        "docker",
        "compose",
        "exec",
        "-T",
        "airflow",
        "cat",
        "/opt/airflow/simple_auth_manager_passwords.json.generated",
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return None

    try:
        payload = json.loads(completed.stdout)
    except json.JSONDecodeError:
        return None

    password = payload.get("admin")
    return str(password) if password else None


def _new_page(browser: Browser) -> Tuple[BrowserContext, Page]:
    context = browser.new_context()
    page = context.new_page()
    return context, page


def validate_streamlit(browser: Browser) -> ValidationResult:
    """Validate Streamlit login and page navigation."""
    result = ValidationResult(name="TRACK 1 - STREAMLIT UI")
    start = time.perf_counter()
    context, page = _new_page(browser)
    _attach_console_watch(page, result)

    try:
        page.goto(STREAMLIT_URL, wait_until="domcontentloaded", timeout=30000)
        page.locator("input[placeholder='Username']").wait_for(timeout=15000)
        page.fill("input[placeholder='Username']", "admin")
        page.fill("input[placeholder='Password']", "wrong-password")
        page.get_by_role("button", name=re.compile("AUTHENTICATE")).click()
        page.get_by_text("Access Denied").wait_for(timeout=10000)
        result.add_validation("Invalid login shows Access Denied")

        page.fill("input[placeholder='Username']", "admin")
        page.fill("input[placeholder='Password']", "shadowdesk")
        page.get_by_role("button", name=re.compile("AUTHENTICATE")).click()
        page.get_by_text("Welcome to Shadow Alpha Trading Terminal").wait_for(timeout=20000)
        result.add_validation("Primary login succeeds")

        page_expectations = {
            "Dashboard": "Open Positions",
            "Signals": "Trading Signals",
            "Trade Execution": "Approve and Manage Trades",
            "Analytics": "Live Portfolio & Trade Statistics",
            "Settings": "Configure Trading Parameters",
        }
        for label, marker in page_expectations.items():
            page.get_by_role("link", name=re.compile(label)).last.click()
            page.get_by_text(marker).first.wait_for(timeout=20000)
            page.get_by_text("💓 System Pulse").wait_for(timeout=10000)
            result.add_validation(f"{label} page renders and keeps session state")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track1", "streamlit_failure")
        result.add_issue(f"Streamlit validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_fastapi(session: requests.Session) -> ValidationResult:
    """Validate FastAPI endpoints used by the dashboard and trading flow."""
    result = ValidationResult(name="TRACK 2 - FASTAPI BACKEND")
    start = time.perf_counter()

    try:
        health = _make_request(session, "GET", f"{FASTAPI_URL}/health", expected_status=[200]).json()
        if health.get("status") != "healthy":
            raise RuntimeError(f"Unexpected health payload: {health}")
        result.add_validation("GET /health returns healthy")

        _make_request(session, "GET", f"{FASTAPI_URL}/health/services", expected_status=[200])
        _make_request(session, "GET", f"{FASTAPI_URL}/trading/signals/AAPL", expected_status=[200])
        _make_request(
            session,
            "POST",
            f"{FASTAPI_URL}/trading/signals/batch",
            expected_status=[200],
            json={"symbols": ["AAPL", "MSFT"], "min_confidence": 0.6},
        )

        order_response = _make_request(
            session,
            "POST",
            f"{FASTAPI_URL}/trading/orders",
            expected_status=[200],
            json={
                "symbol": "AMD",
                "qty": 1,
                "side": "buy",
                "order_type": "limit",
                "limit_price": 100.0,
            },
        ).json()
        order_id = order_response.get("order", {}).get("id")
        if not order_id:
            raise RuntimeError(f"Order ID missing from response: {order_response}")
        result.add_validation("POST /trading/orders creates a limit order")

        orders_payload = _make_request(session, "GET", f"{FASTAPI_URL}/trading/orders", expected_status=[200]).json()
        open_order_ids = {order.get("id") for order in orders_payload.get("orders", [])}
        if order_id not in open_order_ids:
            raise RuntimeError(f"Open order {order_id} not found in order list")
        result.add_validation("GET /trading/orders returns the created order")

        _make_request(session, "DELETE", f"{FASTAPI_URL}/trading/orders/{order_id}", expected_status=[200])
        _make_request(session, "GET", f"{FASTAPI_URL}/trading/positions", expected_status=[200])
        _make_request(
            session,
            "POST",
            f"{FASTAPI_URL}/trading/cycle",
            expected_status=[200],
            json={"symbols": []},
        )
        _make_request(session, "GET", f"{FASTAPI_URL}/account/", expected_status=[200])
        _make_request(session, "GET", f"{FASTAPI_URL}/account/portfolio", expected_status=[200])
        _make_request(session, "GET", f"{FASTAPI_URL}/embeddings/collections", expected_status=[200])

        invalid = _make_request(
            session,
            "GET",
            f"{FASTAPI_URL}/trading/signals/INVALID_SYMBOL",
            expected_status=[404],
        )
        if invalid.status_code != 404:
            raise RuntimeError("Invalid symbol request did not return 404")
        result.add_validation("Invalid symbol returns 404")
    except Exception as exc:
        result.add_issue(f"FastAPI validation failed: {exc}", fatal=True)
    finally:
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_mlflow(browser: Browser, session: requests.Session) -> ValidationResult:
    """Validate MLflow UI and model registry availability."""
    result = ValidationResult(name="TRACK 3 - MLFLOW")
    start = time.perf_counter()
    context, page = _new_page(browser)
    _attach_console_watch(page, result)

    try:
        page.goto(MLFLOW_URL, wait_until="domcontentloaded", timeout=30000)
        if "MLflow" not in page.title():
            raise RuntimeError(f"Unexpected MLflow page title: {page.title()}")
        result.add_validation("MLflow landing page loads")

        models = _make_request(
            session,
            "GET",
            f"{MLFLOW_URL}/api/2.0/mlflow/registered-models/search",
            expected_status=[200],
        ).json()
        model_count = len(models.get("registered_models", []))
        result.add_validation(f"MLflow model registry is reachable ({model_count} registered models)")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track3", "mlflow_failure")
        result.add_issue(f"MLflow validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_prometheus(browser: Browser, session: requests.Session) -> ValidationResult:
    """Validate Prometheus UI routing and query API."""
    result = ValidationResult(name="TRACK 4 - PROMETHEUS")
    start = time.perf_counter()
    context, page = _new_page(browser)
    _attach_console_watch(page, result, ignored_console_patterns=["LRU_CACHE_UNBOUNDED"])

    try:
        page.goto(PROMETHEUS_URL, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_url("**/query", timeout=15000)
        page.get_by_text("Graph").wait_for(timeout=10000)
        result.add_validation("Prometheus UI loads and redirects to /query")

        up_query = _make_request(
            session,
            "GET",
            f"{PROMETHEUS_URL}/api/v1/query",
            expected_status=[200],
            params={"query": "up"},
        ).json()
        up_count = len(up_query.get("data", {}).get("result", []))
        if up_count < 1:
            raise RuntimeError("Prometheus query 'up' returned no series")
        result.add_validation(f"'up' query returns {up_count} series")

        api_series = _wait_for_metric_series(session, "api_http_requests_total")
        if api_series == 0:
            result.add_issue("api_http_requests_total is absent/empty in the current local scrape config")
        else:
            result.add_validation("api_http_requests_total returns series")

        page.goto(f"{PROMETHEUS_URL}/targets", wait_until="domcontentloaded", timeout=30000)
        page.get_by_role("button", name="prometheus 1 / 1 up").wait_for(timeout=10000)
        page.get_by_role("button", name="qdrant 1 / 1 up").wait_for(timeout=10000)
        page.get_by_role("button", name="fastapi 1 / 1 up").wait_for(timeout=10000)
        result.add_validation("Targets page shows configured scrape targets")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track4", "prometheus_failure")
        result.add_issue(f"Prometheus validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_grafana(browser: Browser) -> ValidationResult:
    """Validate Grafana login and Explore access."""
    result = ValidationResult(name="TRACK 5 - GRAFANA")
    start = time.perf_counter()
    context, page = _new_page(browser)
    _attach_console_watch(page, result)

    try:
        page.goto(f"{GRAFANA_URL}/login", wait_until="domcontentloaded", timeout=30000)
        page.locator("input[name='user']").wait_for(timeout=15000)
        page.fill("input[name='user']", "admin")
        page.fill("input[name='password']", "admin")
        page.get_by_role("button", name=re.compile("Log in", re.IGNORECASE)).click()
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_timeout(1500)

        if page.get_by_text("Update your password").count():
            page.get_by_role("button", name=re.compile("Skip", re.IGNORECASE)).click()
            page.wait_for_load_state("domcontentloaded")
            page.wait_for_timeout(1500)

        if "/login" in page.url and page.locator("input[name='user']").count():
            raise RuntimeError("Grafana remained on the login page after authentication")

        result.add_validation("Grafana login succeeds")
        page.goto(f"{GRAFANA_URL}/connections/datasources", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        if not page.locator("text=Prometheus").count():
            result.add_issue("Grafana local stack has no provisioned data sources")
        else:
            result.add_validation("Grafana data source is provisioned")

        page.goto(f"{GRAFANA_URL}/dashboards", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        if page.locator("text=Dashboards").count() and not page.locator("text=ShadowAlpha Overview").count():
            result.add_issue("ShadowAlpha Overview dashboard is not provisioned in the local Grafana instance")
        else:
            result.add_validation("ShadowAlpha Overview dashboard is provisioned")

        page.goto(f"{GRAFANA_URL}/explore", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        result.add_validation("Grafana Explore page loads")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track5", "grafana_failure")
        result.add_issue(f"Grafana validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_airflow(browser: Browser) -> ValidationResult:
    """Validate Airflow login and DAG listing."""
    result = ValidationResult(name="TRACK 6 - AIRFLOW")
    start = time.perf_counter()
    context, page = _new_page(browser)
    _attach_console_watch(
        page,
        result,
        ignored_console_patterns=["Failed to load resource: the server responded with a status of 401 (Unauthorized)"],
    )
    airflow_password = _get_airflow_password()

    try:
        if not airflow_password:
            raise RuntimeError("Could not retrieve the generated Airflow admin password")

        page.goto(f"{AIRFLOW_URL}/login/", wait_until="domcontentloaded", timeout=30000)
        page.locator("input[name='username']").wait_for(timeout=15000)
        page.fill("input[name='username']", "admin")
        page.fill("input[name='password']", airflow_password)
        page.get_by_role("button", name=re.compile("Sign in|Log in", re.IGNORECASE)).click()
        page.wait_for_load_state("domcontentloaded")
        page.get_by_role("link", name=re.compile("Dags", re.IGNORECASE)).click()
        page.wait_for_load_state("domcontentloaded")
        page.get_by_role("link", name="autonomous_trading", exact=True).wait_for(timeout=20000)
        page.get_by_role("link", name="autonomous_trading_daily_retrain", exact=True).wait_for(timeout=20000)
        page.get_by_role("link", name="stock_ml_pipeline", exact=True).wait_for(timeout=20000)
        result.add_validation("Airflow login succeeds and expected DAGs are visible")

        page.get_by_role("link", name="autonomous_trading", exact=True).click()
        page.wait_for_load_state("domcontentloaded")
        page.get_by_text("Overview").first.wait_for(timeout=10000)
        page.get_by_text("Tasks").first.wait_for(timeout=10000)
        result.add_validation("Airflow DAG details and task views are reachable")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track6", "airflow_failure")
        result.add_issue(f"Airflow validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_vault(session: requests.Session) -> ValidationResult:
    """Validate Vault health and expected secret paths."""
    result = ValidationResult(name="TRACK 7 - VAULT")
    start = time.perf_counter()
    headers = {"X-Vault-Token": "shadowdesk-devtoken"}

    try:
        _make_request(session, "GET", f"{VAULT_URL}/v1/sys/health", expected_status=[200])
        _make_request(
            session,
            "GET",
            f"{VAULT_URL}/v1/auth/token/lookup-self",
            expected_status=[200],
            headers=headers,
        )
        result.add_validation("Vault health and token authentication succeed")

        for path in ("trading", "alpaca", "dashboard"):
            response = _make_request(
                session,
                "GET",
                f"{VAULT_URL}/v1/secret/data/{path}",
                expected_status=[200, 404],
                headers=headers,
            )
            if response.status_code == 404:
                result.add_issue(f"Vault secret secret/data/{path} is not seeded in the local stack")
            else:
                result.add_validation(f"Vault secret secret/data/{path} is readable")
    except Exception as exc:
        result.add_issue(f"Vault validation failed: {exc}", fatal=True)
    finally:
        result.duration_seconds = time.perf_counter() - start

    return result


def validate_storage(browser: Browser, session: requests.Session) -> ValidationResult:
    """Validate MinIO and Qdrant availability and empty-state behavior."""
    result = ValidationResult(name="TRACK 8 - MINIO + QDRANT")
    start = time.perf_counter()

    context, page = _new_page(browser)
    _attach_console_watch(page, result)
    try:
        page.goto(f"{MINIO_CONSOLE_URL}/login", wait_until="domcontentloaded", timeout=30000)
        page.locator("input").nth(0).fill("shadowdesk")
        page.locator("input").nth(1).fill("shadowdesk123")
        page.get_by_role("button").last.click()
        page.wait_for_timeout(1500)
        result.add_validation("MinIO console login flow completes")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track8", "minio_failure")
        result.add_issue(f"MinIO console validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()

    try:
        _make_request(session, "GET", f"{MINIO_API_URL}/minio/health/live", expected_status=[200])
        _make_request(session, "GET", f"{MINIO_API_URL}/minio/health/ready", expected_status=[200])
        result.add_validation("MinIO health endpoints respond")
    except Exception as exc:
        result.add_issue(f"MinIO API validation failed: {exc}", fatal=True)

    try:
        from minio import Minio

        client = Minio(
            "localhost:19000",
            access_key="shadowdesk",
            secret_key="shadowdesk123",
            secure=False,
        )
        bucket_names = {bucket.name for bucket in client.list_buckets()}
        expected_buckets = {"stock-data", "shadowdesk-data", "shadowdesk-models"}
        missing = sorted(expected_buckets - bucket_names)
        if missing:
            result.add_issue(f"Missing MinIO buckets in local seed state: {', '.join(missing)}")
        else:
            result.add_validation("Expected MinIO buckets are present")
    except Exception as exc:
        result.add_issue(f"MinIO bucket inspection failed: {exc}", fatal=True)

    context, page = _new_page(browser)
    _attach_console_watch(page, result)
    try:
        page.goto(f"{QDRANT_URL}/dashboard", wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1000)
        result.add_validation("Qdrant dashboard loads")
    except Exception as exc:
        screenshot = _save_failure_screenshot(page, "track8", "qdrant_failure")
        result.add_issue(f"Qdrant dashboard validation failed: {exc}. Screenshot: {screenshot}", fatal=True)
    finally:
        context.close()

    try:
        root_response = _make_request(session, "GET", f"{QDRANT_URL}/", expected_status=[200]).json()
        if "qdrant" not in str(root_response.get("title", "")).lower():
            raise RuntimeError(f"Unexpected Qdrant root payload: {root_response}")
        result.add_validation("Qdrant root endpoint responds")

        collections_response = _make_request(session, "GET", f"{QDRANT_URL}/collections", expected_status=[200]).json()
        collection_names = {
            collection.get("name")
            for collection in collections_response.get("result", {}).get("collections", [])
        }
        if "stock_embeddings" not in collection_names:
            result.add_issue("Qdrant collection stock_embeddings is not seeded in the local stack")
        else:
            result.add_validation(f"Qdrant has {len(collection_names)} seeded collections")

        health_response = session.get(f"{QDRANT_URL}/health", timeout=30)
        if health_response.status_code == 200:
            result.add_validation("Qdrant /health endpoint responds")
        else:
            result.add_validation("Qdrant health is verified via the root and collections endpoints")
    except Exception as exc:
        result.add_issue(f"Qdrant validation failed: {exc}", fatal=True)
    finally:
        result.duration_seconds = time.perf_counter() - start

    return result


def _print_result(result: ValidationResult) -> None:
    print(f"\n{result.name}")
    print(f"Status: {result.status}")
    print(f"Duration: {result.duration_seconds:.2f}s")
    if result.validated:
        print("Validated:")
        for item in result.validated:
            print(f"  - {item}")
    if result.issues:
        print("Issues:")
        for item in result.issues:
            print(f"  - {item}")


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments."""
    parser = argparse.ArgumentParser(description="Validate the local ShadowDesk stack")
    parser.add_argument(
        "--track",
        action="append",
        choices=[
            "streamlit",
            "fastapi",
            "mlflow",
            "prometheus",
            "grafana",
            "airflow",
            "vault",
            "storage",
        ],
        help="Run only the selected track(s). Defaults to all.",
    )
    parser.add_argument(
        "--headed",
        action="store_true",
        help="Run browser-based checks in headed mode.",
    )
    parser.add_argument(
        "--bootstrap",
        action="store_true",
        help="Seed local Grafana, Vault, MinIO, and Qdrant before validation.",
    )
    return parser.parse_args()


def main() -> int:
    """Run the selected local validation tracks."""
    args = parse_args()
    selected_tracks = args.track or [
        "streamlit",
        "fastapi",
        "mlflow",
        "prometheus",
        "grafana",
        "airflow",
        "vault",
        "storage",
    ]
    session = requests.Session()

    if args.bootstrap:
        print("Bootstrapping local stack state...")
        bootstrap_local_stack(session=session)

    browser_tracks = {"streamlit", "mlflow", "prometheus", "grafana", "airflow", "storage"}
    if browser_tracks.intersection(selected_tracks) and sync_playwright is None:
        print(
            "Playwright is not installed. Install it with `pip install -r requirements.txt` and "
            "`python -m playwright install chromium`.",
            file=sys.stderr,
        )
        return 2

    track_functions: Dict[str, Callable[..., ValidationResult]] = {
        "streamlit": validate_streamlit,
        "fastapi": validate_fastapi,
        "mlflow": validate_mlflow,
        "prometheus": validate_prometheus,
        "grafana": validate_grafana,
        "airflow": validate_airflow,
        "vault": validate_vault,
        "storage": validate_storage,
    }

    results: List[ValidationResult] = []

    if browser_tracks.intersection(selected_tracks):
        with sync_playwright() as playwright:
            browser = playwright.chromium.launch(headless=not args.headed)
            for track in selected_tracks:
                validator = track_functions[track]
                if track in {"streamlit", "grafana", "airflow"}:
                    results.append(validator(browser))
                elif track in {"mlflow", "prometheus", "storage"}:
                    results.append(validator(browser, session))
                elif track == "fastapi":
                    results.append(validator(session))
                elif track == "vault":
                    results.append(validator(session))
            browser.close()
    else:
        for track in selected_tracks:
            validator = track_functions[track]
            if track == "fastapi":
                results.append(validator(session))
            elif track == "vault":
                results.append(validator(session))

    failing = 0
    for result in results:
        _print_result(result)
        if result.status == "FAIL":
            failing += 1

    print("\nSummary")
    print(f"  - Tracks run: {len(results)}")
    print(f"  - Passed: {sum(result.status == 'PASS' for result in results)}")
    print(f"  - Failed: {failing}")
    print(f"  - With findings: {sum(bool(result.issues) for result in results)}")

    return 1 if failing else 0


if __name__ == "__main__":
    raise SystemExit(main())
