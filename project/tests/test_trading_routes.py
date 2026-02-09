from fastapi.testclient import TestClient

from cluster_b.api.main import app
from cluster_b.api.routes import trading


def test_get_signals_batch_uses_signal_service(monkeypatch):
    class StubSignals:
        def get_signals(self, symbols, min_confidence=0.6):
            return [
                {
                    "symbol": "AAPL",
                    "signal": "BUY",
                    "confidence": 0.82,
                    "current_price": 185.1,
                    "timestamp": "2026-03-29T16:00:00Z",
                    "prediction": 1,
                }
            ]

    class StubExecutor:
        signals = StubSignals()

    monkeypatch.setattr(trading, "get_executor", lambda request: StubExecutor())

    client = TestClient(app)
    response = client.post(
        "/trading/signals/batch",
        json={"symbols": ["AAPL"], "min_confidence": 0.6},
    )

    assert response.json()[0]["signal"] == "BUY"


def test_run_trading_cycle_accepts_cycle_request(monkeypatch):
    class StubExecutor:
        def run_cycle(self, symbols):
            return {"symbols": symbols, "executions": [], "errors": []}

    monkeypatch.setattr(trading, "get_executor", lambda request: StubExecutor())

    client = TestClient(app)
    response = client.post("/trading/cycle", json={"symbols": ["AAPL", "MSFT"]})

    assert response.json()["symbols"] == ["AAPL", "MSFT"]
