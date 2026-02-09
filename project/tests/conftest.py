from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient


@pytest.fixture
def test_client():
    from cluster_b.api.main import app

    return TestClient(app)


@pytest.fixture
def stub_broker():
    broker = MagicMock()
    broker.get_account_info.return_value = {...}
    broker.get_portfolio.return_value = {...}
    return broker


@pytest.fixture
def stub_signals():
    signals = MagicMock()
    signals.get_signals.return_value = [...]
    return signals


@pytest.fixture
def stub_executor():
    executor = MagicMock()
    executor.can_trade.return_value = True
    return executor
