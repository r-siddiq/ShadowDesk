from fastapi.testclient import TestClient

from cluster_b.api.main import app
from cluster_b.trading.broker import AlpacaBroker
from cluster_b.trading.executor import TradingExecutor


class StubSignals:
    def generate_signal(self, symbol: str) -> dict:
        return {
            "symbol": symbol,
            "signal": "BUY" if symbol != "MSFT" else "HOLD",
            "confidence": 0.75 if symbol != "MSFT" else 0.5,
            "current_price": 125.0,
            "timestamp": "2026-03-29T00:00:00",
            "prediction": 1 if symbol != "MSFT" else -1,
        }

    def get_signals(self, symbols: list[str], min_confidence: float = 0.6) -> list[dict]:
        return [
            self.generate_signal(symbol)
            for symbol in symbols
            if self.generate_signal(symbol)["confidence"] >= min_confidence
        ]


def build_client() -> TestClient:
    broker = AlpacaBroker(demo=True)
    app.state.broker = broker
    app.state.executor = TradingExecutor(broker=broker, signals=StubSignals())
    return TestClient(app)


def test_account_endpoint_returns_demo_account() -> None:
    client = build_client()

    response = client.get("/account/")

    assert response.status_code == 200


def test_orders_endpoint_supports_submit_list_and_cancel() -> None:
    client = build_client()

    create_response = client.post(
        "/trading/orders",
        json={
            "symbol": "AMD",
            "qty": 5,
            "side": "buy",
            "order_type": "limit",
            "limit_price": 101.25,
        },
    )
    list_response = client.get("/trading/orders")
    order_id = create_response.json()["order"]["id"]
    cancel_response = client.delete(f"/trading/orders/{order_id}")

    assert (
        create_response.status_code,
        list_response.json()["count"],
        cancel_response.status_code,
    ) == (200, 1, 200)


def test_signal_batch_endpoint_returns_signal_payloads() -> None:
    client = build_client()

    response = client.post(
        "/trading/signals/batch",
        json={"symbols": ["AAPL", "MSFT"], "min_confidence": 0.6},
    )

    assert response.json()[0]["symbol"] == "AAPL"


def test_trading_cycle_endpoint_returns_cycle_results() -> None:
    client = build_client()

    response = client.post("/trading/cycle", json={"symbols": ["AAPL", "MSFT"]})

    assert "positions_after" in response.json()
