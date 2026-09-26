# Application service layer
from domain.model import OrderEntity

class OrderApplicationService:
    def create_order(self, order_id: str, amount: float) -> OrderEntity:
        return OrderEntity(order_id=order_id, amount=amount)
