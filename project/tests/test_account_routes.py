from fastapi.testclient import TestClient

from cluster_b.api.main import app
from cluster_b.api.routes import account


def test_get_portfolio_uses_portfolio_value_without_double_counting_cash(monkeypatch):
    class StubBroker:
        def get_account(self):
            return {
                "portfolio_value": 106175,
                "cash": 75000,
            }

        def get_positions(self):
            return [
                {
                    "symbol": "AAPL",
                    "qty": 10,
                    "avg_entry_price": 175.5,
                    "market_value": 1825,
                    "cost_basis": 1755,
                    "unrealized_pl": 70,
                    "unrealized_plpc": 0.0399,
                    "current_price": 182.5,
                }
            ]

    monkeypatch.setattr(account, "get_broker", lambda request: StubBroker())

    client = TestClient(app)
    response = client.get("/account/portfolio")

    assert response.json()["total_value"] == 106175.0


def test_get_trade_history_returns_broker_fills(monkeypatch):
    class StubBroker:
        def get_filled_orders(self, limit=50):
            return [
                {
                    "id": "fill-1",
                    "symbol": "AAPL",
                    "side": "buy",
                    "qty": 3,
                    "filled_avg_price": 175.25,
                    "status": "filled",
                    "submitted_at": "2026-03-29T16:00:00Z",
                    "filled_at": "2026-03-29T16:00:01Z",
                }
            ]

    monkeypatch.setattr(account, "get_broker", lambda request: StubBroker())

    client = TestClient(app)
    response = client.get("/account/history")

    assert response.json()[0]["symbol"] == "AAPL"
