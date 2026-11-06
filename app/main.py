
from fastapi import FastAPI

from app.database import Base, engine
from app import models
from app.routers.orders import router as orders_router


Base.metadata.create_all(bind=engine)


app = FastAPI(
    title="A PRUEBA - Idempotency API",
    description=(
        "A REST API demonstrating idempotent "
        "order creation and request handling."
    ),
    version="1.0.0",
)


app.include_router(orders_router)


@app.get("/", tags=["Health"])
def root():
    return {
        "message": "A PRUEBA - Idempotency API",
        "status": "running",
    }
