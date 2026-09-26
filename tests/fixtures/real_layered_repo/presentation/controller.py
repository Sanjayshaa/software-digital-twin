# Presentation layer controller (Clean State)
from application.service import OrderApplicationService

class OrderController:
    def __init__(self):
        self.service = OrderApplicationService()

    def handle_create(self, order_id: str, amount: float):
        return self.service.create_order(order_id, amount)
