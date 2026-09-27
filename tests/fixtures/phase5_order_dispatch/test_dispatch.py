import pytest
from dispatcher import OrderDispatcher

def test_dispatch_success():
    dispatcher = OrderDispatcher()
    res = dispatcher.dispatch_order("ord-1", "sku-99", 2)
    assert res["status"] == "DISPATCHED"

def test_dispatch_invalid_qty():
    dispatcher = OrderDispatcher()
    with pytest.raises(ValueError):
        dispatcher.dispatch_order("ord-2", "sku-99", 0)
