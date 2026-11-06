import pytest
from fastapi import HTTPException

from app.models import IdempotencyKey, Order, Product
from app.schemas import OrderCreate
from app.services.order_service import create_order


def test_same_key_and_same_payload_returns_original_order(db_session):
    order_data = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1},
        ],
    )

    first_status, first_response = create_order(
        db=db_session,
        order_data=order_data,
        idempotency_key="test-idempotency-001",
    )

    second_status, second_response = create_order(
        db=db_session,
        order_data=order_data,
        idempotency_key="test-idempotency-001",
    )

    assert first_status == 201
    assert second_status == 201
    assert second_response == first_response

    assert db_session.query(Order).count() == 1
    assert db_session.query(IdempotencyKey).count() == 1

    keyboard = db_session.get(Product, 1)
    mouse = db_session.get(Product, 2)

    assert keyboard.stock == 8
    assert mouse.stock == 19


def test_same_key_with_different_payload_returns_conflict(db_session):
    first_order = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 1, "quantity": 2},
        ],
    )

    different_order = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 1, "quantity": 3},
        ],
    )

    first_status, first_response = create_order(
        db=db_session,
        order_data=first_order,
        idempotency_key="test-idempotency-conflict-001",
    )

    with pytest.raises(HTTPException) as exc_info:
        create_order(
            db=db_session,
            order_data=different_order,
            idempotency_key="test-idempotency-conflict-001",
        )

    assert first_status == 201
    assert exc_info.value.status_code == 409

    assert db_session.query(Order).count() == 1
    assert db_session.query(IdempotencyKey).count() == 1

    keyboard = db_session.get(Product, 1)

    assert keyboard.stock == 8