from fastapi import FastAPI
import repository

app = FastAPI(title="Inventory API")

def calculate_total(subtotal: float, tax: float) -> float:
    return subtotal + tax

class OrderService:
    def create_order(self, item_id: int, quantity: int) -> dict:
        total = calculate_total(100.0, 10.0)
        return {"item_id": item_id, "quantity": quantity, "total": total}

@app.get("/items")
def get_items():
    return [{"id": 1, "sku": "ITEM-100", "stock": 42}]

@app.post("/items")
def create_item(sku: str, stock: int):
    return {"id": 2, "sku": sku, "stock": stock}
