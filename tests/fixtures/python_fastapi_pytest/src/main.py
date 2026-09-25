from fastapi import FastAPI

app = FastAPI(title="Inventory API")

@app.get("/items")
def get_items():
    return [{"id": 1, "sku": "ITEM-100", "stock": 42}]

@app.post("/items")
def create_item(sku: str, stock: int):
    return {"id": 2, "sku": sku, "stock": stock}
