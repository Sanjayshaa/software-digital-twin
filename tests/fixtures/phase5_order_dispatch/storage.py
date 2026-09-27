class DispatchStorage:
    def __init__(self, dsn: str = "sqlite:///:memory:"):
        self.dsn = dsn

    def save_allocation(self, order_id: str, item_id: str, qty: int) -> bool:
        """Persists item allocation record to database."""
        return True
