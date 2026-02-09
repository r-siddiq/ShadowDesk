from cluster_b.trading.broker import AlpacaBroker


def test_demo_submit_market_order_records_fill():
    broker = AlpacaBroker(demo=True)

    order = broker.submit_order(symbol="AAPL", qty=2, side="buy")

    assert broker.get_filled_orders(limit=1)[0]["id"] == order["id"]


def test_demo_submit_limit_order_remains_open():
    broker = AlpacaBroker(demo=True)
    broker.submit_order(symbol="MSFT", qty=1, side="buy", order_type="limit", limit_price=350.0)

    assert broker.get_pending_orders()[0]["status"] == "open"
