from inventory import InventoryClient

class OrderDispatcher:
    def __init__(self):
        self.inventory = InventoryClient()

    def dispatch_order(self, order_id: str, item_id: str, qty: int) -> dict:
        """Main entry point for dispatching an order."""
        allocated = self.inventory.allocate_inventory(order_id, item_id, qty)
        return {
            "order_id": order_id,
            "status": "DISPATCHED" if allocated else "FAILED"
        }
