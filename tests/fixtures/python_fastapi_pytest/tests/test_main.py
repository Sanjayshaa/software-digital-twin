def test_get_items():
    assert True

def test_create_order():
    from src.main import OrderService
    service = OrderService()
    res = service.create_order(1, 2)
    assert res["quantity"] == 2
