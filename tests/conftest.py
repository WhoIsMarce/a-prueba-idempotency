import pytest
from sqlalchemy import create_engine, delete
from sqlalchemy.orm import sessionmaker

from app.database import Base
from app.models import IdempotencyKey, Order, OrderItem, Product


TEST_DATABASE_URL = (
    "postgresql+psycopg://"
    "app_user:local_dev_password"
    "@localhost:5433/idempotency_test_db"
)


@pytest.fixture(scope="session")
def test_engine():
    engine = create_engine(
        TEST_DATABASE_URL,
        pool_pre_ping=True,
    )

    Base.metadata.create_all(bind=engine)

    yield engine

    engine.dispose()


@pytest.fixture()
def db_session(test_engine):
    TestingSessionLocal = sessionmaker(
        bind=test_engine,
        autoflush=False,
        autocommit=False,
    )

    session = TestingSessionLocal()

    def clean_database():
        session.execute(delete(OrderItem))
        session.execute(delete(IdempotencyKey))
        session.execute(delete(Order))
        session.execute(delete(Product))
        session.commit()

    clean_database()

    session.add_all([
        Product(
            id=1,
            name="Keyboard",
            price=50.00,
            stock=10,
        ),
        Product(
            id=2,
            name="Mouse",
            price=25.00,
            stock=20,
        ),
    ])
    session.commit()

    yield session

    session.close()

    cleanup_session = TestingSessionLocal()
    try:
        cleanup_session.execute(delete(OrderItem))
        cleanup_session.execute(delete(IdempotencyKey))
        cleanup_session.execute(delete(Order))
        cleanup_session.execute(delete(Product))
        cleanup_session.commit()
    finally:
        cleanup_session.close()