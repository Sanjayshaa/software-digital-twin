from storage import DispatchStorage

class InventoryClient:
    def __init__(self):
        self.storage = DispatchStorage()

    def allocate_inventory(self, order_id: str, item_id: str, qty: int) -> bool:
        """Allocates stock and commits to storage."""
        if qty <= 0:
            raise ValueError("Quantity must be positive")
        return self.storage.save_allocation(order_id, item_id, qty)
