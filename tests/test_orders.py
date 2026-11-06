import pytest
from decimal import Decimal
from fastapi import HTTPException

from app.models import Order, IdempotencyKey, Product
from app.schemas import OrderCreate
from app.services.order_service import create_order


def test_create_order_successfully(db_session):
    order_data = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1},
        ],
    )

    status_code, response_body = create_order(
        db=db_session,
        order_data=order_data,
        idempotency_key="test-order-001",
    )

    assert status_code == 201
    assert response_body["customer_id"] == 42
    assert response_body["status"] == "created"
    assert Decimal(response_body["total_amount"]) == Decimal("125.00")

    order = db_session.get(Order, response_body["id"])

    assert order is not None
    assert len(order.items) == 2

    keyboard = db_session.get(Product, 1)
    mouse = db_session.get(Product, 2)

    assert keyboard.stock == 8
    assert mouse.stock == 19


def test_nonexistent_product_returns_404(db_session):
    order_data = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 9999, "quantity": 1},
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        create_order(
            db=db_session,
            order_data=order_data,
            idempotency_key="test-product-404",
        )

    assert exc_info.value.status_code == 404
    assert db_session.query(Order).count() == 0
    assert db_session.query(IdempotencyKey).count() == 0


def test_insufficient_stock_returns_409(db_session):
    order_data = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 1, "quantity": 11},
        ],
    )

    with pytest.raises(HTTPException) as exc_info:
        create_order(
            db=db_session,
            order_data=order_data,
            idempotency_key="test-stock-409",
        )

    assert exc_info.value.status_code == 409
    assert db_session.query(Order).count() == 0
    assert db_session.query(IdempotencyKey).count() == 0

    keyboard = db_session.get(Product, 1)
    assert keyboard.stock == 10