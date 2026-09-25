from fastapi import FastAPI

app = FastAPI(title="Order Service")

@app.post("/orders")
def create_order():
    return {"order_id": "ORD-123", "status": "PENDING"}
