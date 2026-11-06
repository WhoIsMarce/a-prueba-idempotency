
import hashlib
import json
from decimal import Decimal

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import (
    IdempotencyKey,
    Order,
    OrderItem,
    Product,
)
from app.schemas import OrderCreate, OrderResponse


def calculate_request_hash(order_data: OrderCreate) -> str:
    """
    Generate a stable SHA-256 hash from an order request.
    """

    normalized_data = order_data.model_dump(mode="json")

    serialized_data = json.dumps(
        normalized_data,
        sort_keys=True,
        separators=(",", ":"),
    )

    return hashlib.sha256(
        serialized_data.encode("utf-8")
    ).hexdigest()


def create_order(
    db: Session,
    order_data: OrderCreate,
    idempotency_key: str,
) -> tuple[int, dict]:
    """
    Create an order using an atomic idempotency strategy.

    Returns:
        A tuple containing the original HTTP status and response body.
    """

    request_hash = calculate_request_hash(order_data)

    with db.begin():

        # 1. Register the idempotency key atomically.

        statement = (
            insert(IdempotencyKey)
            .values(
                customer_id=order_data.customer_id,
                key=idempotency_key,
                request_hash=request_hash,
            )
            .on_conflict_do_nothing(
                constraint="uq_customer_idempotency_key"
            )
            .returning(IdempotencyKey.id)
        )

        inserted_id = db.execute(statement).scalar_one_or_none()

        # 2. Handle an existing key.

        if inserted_id is None:
            existing_key = db.execute(
                select(IdempotencyKey).where(
                    IdempotencyKey.customer_id
                    == order_data.customer_id,
                    IdempotencyKey.key == idempotency_key,
                )
            ).scalar_one()

            if existing_key.request_hash != request_hash:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        "This Idempotency-Key was already used "
                        "with a different request payload."
                    ),
                )

            if (
                existing_key.response_body is None
                or existing_key.response_status is None
            ):
                raise HTTPException(
                    status_code=409,
                    detail="The original request has no stored response.",
                )

            return (
                existing_key.response_status,
                existing_key.response_body,
            )

        # 3. Consolidate repeated product IDs.

        quantities = {}

        for item in order_data.items:
            quantities[item.product_id] = (
                quantities.get(item.product_id, 0)
                + item.quantity
            )

        product_ids = sorted(quantities.keys())

        # 4. Lock products in a consistent order.

        products = db.execute(
            select(Product)
            .where(Product.id.in_(product_ids))
            .order_by(Product.id)
            .with_for_update()
        ).scalars().all()

        products_by_id = {
            product.id: product
            for product in products
        }

        # 5. Validate product existence and stock.

        if len(products_by_id) != len(product_ids):
            raise HTTPException(
                status_code=404,
                detail="One or more products do not exist.",
            )

        for product_id, quantity in quantities.items():
            product = products_by_id[product_id]

            if product.stock < quantity:
                raise HTTPException(
                    status_code=409,
                    detail=(
                        f"Insufficient stock for product {product_id}."
                    ),
                )

        # 6. Calculate total and update stock.

        total_amount = Decimal("0.00")
        order_items = []

        for product_id, quantity in quantities.items():
            product = products_by_id[product_id]

            unit_price = product.price
            total_amount += unit_price * quantity

            product.stock -= quantity

            order_items.append(
                OrderItem(
                    product_id=product_id,
                    quantity=quantity,
                    unit_price=unit_price,
                )
            )

        # 7. Create order and items.

        order = Order(
            customer_id=order_data.customer_id,
            status="created",
            total_amount=total_amount,
            items=order_items,
        )

        db.add(order)
        db.flush()

        # 8. Build a JSON-compatible response.

        response_body = OrderResponse.model_validate(
            order
        ).model_dump(mode="json")

        response_status = 201

        # 9. Store the original response.

        idempotency_record = db.execute(
            select(IdempotencyKey).where(
                IdempotencyKey.id == inserted_id
            )
        ).scalar_one()

        idempotency_record.response_status = response_status
        idempotency_record.response_body = response_body
        idempotency_record.order_id = order.id

    # The transaction commits here.

    return response_status, response_body
