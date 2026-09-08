from service.app import app


def test_create_order():
    client = app.test_client()

    response = client.post(
        "/orders",
        headers={
            "Idempotency-Key": "test-key-001"
        },
        json={
            "student_id": "S001",
            "restaurant_id": "R001",
            "items": [
                {
                    "item_id": "I001",
                    "quantity": 2
                }
            ]
        }
    )

    assert response.status_code == 201
    assert "order_id" in response.json


def test_get_missing_order():
    client = app.test_client()

    response = client.get("/orders/does-not-exist")

    assert response.status_code == 404


def test_invalid_order():
    client = app.test_client()

    response = client.post(
        "/orders",
        headers={
            "Idempotency-Key": "test-key-002"
        },
        json={
            "student_id": "S001"
        }
    )

    assert response.status_code == 422


def test_idempotency():
    client = app.test_client()

    order_data = {
        "student_id": "S002",
        "restaurant_id": "R001",
        "items": [
            {
                "item_id": "I001",
                "quantity": 1
            }
        ]
    }

    first_response = client.post(
        "/orders",
        headers={
            "Idempotency-Key": "unique-key-001"
        },
        json=order_data
    )

    second_response = client.post(
        "/orders",
        headers={
            "Idempotency-Key": "unique-key-001"
        },
        json=order_data
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert first_response.json["order_id"] == second_response.json["order_id"]
    