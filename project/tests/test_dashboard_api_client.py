from dashboard.utils.api_client import TradingAPIClient


def test_get_orders_extracts_order_list(monkeypatch):
    client = TradingAPIClient()
    monkeypatch.setattr(
        client,
        "_request",
        lambda method, endpoint, **kwargs: {
            "orders": [{"id": "demo-order"}],
            "count": 1,
        },
    )

    assert client.get_orders() == [{"id": "demo-order"}]


def test_get_pending_signals_filters_hold(monkeypatch):
    client = TradingAPIClient()
    monkeypatch.setattr(
        client,
        "get_signals_batch",
        lambda symbols, min_confidence=0.6: [
            {"symbol": "AAPL", "signal": "BUY", "confidence": 0.8},
            {"symbol": "MSFT", "signal": "HOLD", "confidence": 0.9},
            {"symbol": "NVDA", "signal": "SELL", "confidence": 0.7},
        ],
    )

    assert [signal["symbol"] for signal in client.get_pending_signals(["AAPL", "MSFT", "NVDA"])] == [
        "AAPL",
        "NVDA",
    ]
