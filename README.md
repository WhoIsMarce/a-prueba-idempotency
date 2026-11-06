# A PRUEBA — Idempotency API

A REST API built with **FastAPI and PostgreSQL** to demonstrate how idempotency prevents duplicate order creation when clients retry requests.

## The Problem

Imagine a client submits an order. The server processes it successfully, but the response is delayed or lost.

The client cannot determine whether the order was created, so it retries the request.

Without an idempotency mechanism, the backend may create the same order twice, potentially charging the customer more than once or decrementing inventory incorrectly.

## The Solution

This API implements idempotent order creation through the `Idempotency-Key` HTTP header.

The API guarantees the following behavior:

| Scenario | HTTP response | Behavior |
| --- | ---: | --- |
| First request with a new key | `201 Created` | Creates and stores the order |
| Same key and same payload | `201 Created` | Returns the original response |
| Same key with a different payload | `409 Conflict` | Rejects the request |
| Insufficient stock | `409 Conflict` | Rejects the order and rolls back the transaction |
| Product does not exist | `404 Not Found` | Rejects the order and rolls back the transaction |

The idempotency key is scoped to the customer.

## Tech Stack

- **Python 3.12**
- **FastAPI**
- **PostgreSQL 17**
- **SQLAlchemy 2.x**
- **Pydantic**
- **pytest**
- **Docker Compose**

## Architecture

The application separates HTTP handling, data models, validation schemas, database configuration, and business logic.

```text
app/
├── main.py
├── database.py
├── models.py
├── schemas.py
├── routers/
│   └── orders.py
└── services/
    └── order_service.py

tests/
├── conftest.py
├── test_orders.py
├── test_idempotency.py
└── test_concurrency.py
```

### Database Design

The database uses four tables:

- `products`: product information, prices, and inventory.
- `orders`: customer orders and their totals.
- `order_items`: products and quantities associated with each order.
- `idempotency_keys`: request hashes and stored responses.

A unique database constraint on `(customer_id, key)` prevents duplicate key registration.

The implementation uses PostgreSQL's atomic `INSERT ... ON CONFLICT DO NOTHING` operation and database transactions to handle concurrent requests safely.

## API Endpoints

| Method | Endpoint | Description |
| --- | --- | --- |
| `GET` | `/` | Health check |
| `POST` | `/orders` | Create an idempotent order |
| `GET` | `/orders/{order_id}` | Retrieve an existing order |

Interactive API documentation is available through Swagger UI at `/docs`.

## Example Request

```http
POST /orders
Content-Type: application/json
Idempotency-Key: order-2026-001
```

```json
{
  "customer_id": 42,
  "items": [
    {
      "product_id": 1,
      "quantity": 2
    },
    {
      "product_id": 2,
      "quantity": 1
    }
  ]
}
```

## Running Locally

### Prerequisites

- Python 3.12 or newer (Python 3.12 is the tested version).
- Docker Desktop with Docker Compose.
- Git.

### 1. Clone the repository

```bash
git clone <REPOSITORY_URL>
cd a-prueba-idempotency
```

Replace `<REPOSITORY_URL>` with the repository URL.

### 2. Create and activate a virtual environment

```bash
python -m venv .venv
source .venv/Scripts/activate
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure environment variables

```bash
cp .env.example .env
```

The `.env` file contains the local database connection string.

### 5. Start PostgreSQL

```bash
docker compose up -d
```

The database is exposed on port `5433` on the host.

### 6. Start the API

```bash
uvicorn app.main:app --reload
```

The API is available at:

`http://127.0.0.1:8000`

Swagger UI:

`http://127.0.0.1:8000/docs`

## Running Tests

The test suite uses a separate database named `idempotency_test_db`.

Create it once:

```bash
docker compose exec db psql -U app_user -d postgres -c "CREATE DATABASE idempotency_test_db;"
```

Run the tests:

```bash
python -m pytest tests/ -v
```

The tests cover:

- Successful order creation.
- Repeated requests with the same idempotency key and payload.
- Reuse of a key with a different payload.
- Concurrent requests using the same key.
- Nonexistent products.
- Insufficient inventory and transaction rollback.

## Engineering Considerations

- **Atomicity:** idempotency registration and order creation happen within a database transaction.
- **Concurrency:** PostgreSQL's unique constraint and atomic insert prevent two requests from registering the same customer/key pair.
- **Payload integrity:** a SHA-256 hash identifies whether a repeated key is associated with the same request payload.
- **Inventory consistency:** product rows are locked in a consistent order before stock validation and updates.
- **Response persistence:** the original HTTP status and response body are stored and reused for retries.

## Current Scope and Limitations

This project is a focused demonstration of idempotent order creation.

It does not currently include:

- User authentication or authorization.
- Idempotency-key expiration or cleanup.
- Database migration tooling.
- Cloud deployment or production infrastructure.

The customer identifier is supplied in the request body for demonstration purposes. A production system should derive customer identity from an authenticated context.

## Project Goal

**A PRUEBA** explores practical backend engineering problems through reproducible experiments, implementation, testing, and technical documentation.

The focus is on API reliability, database consistency, and developer experience.
