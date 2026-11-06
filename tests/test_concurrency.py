from concurrent.futures import ThreadPoolExecutor
from threading import Barrier

from sqlalchemy.orm import sessionmaker

from app.models import IdempotencyKey, Order, Product
from app.schemas import OrderCreate
from app.services.order_service import create_order


def test_concurrent_requests_with_same_key_create_one_order(
    test_engine,
    db_session,
):
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    order_data = OrderCreate(
        customer_id=42,
        items=[
            {"product_id": 1, "quantity": 2},
            {"product_id": 2, "quantity": 1},
        ],
    )

    barrier = Barrier(2)

    def submit_order():
        db = TestingSessionLocal()

        try:
            barrier.wait(timeout=10)

            return create_order(
                db=db,
                order_data=order_data,
                idempotency_key="test-concurrency-001",
            )
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as executor:
        future_one = executor.submit(submit_order)
        future_two = executor.submit(submit_order)

        result_one = future_one.result(timeout=20)
        result_two = future_two.result(timeout=20)

    assert result_one[0] == 201
    assert result_two[0] == 201

    assert result_one[1] == result_two[1]

    assert db_session.query(Order).count() == 1
    assert db_session.query(IdempotencyKey).count() == 1

    keyboard = db_session.get(Product, 1)
    mouse = db_session.get(Product, 2)

    assert keyboard.stock == 8
    assert mouse.stock == 19