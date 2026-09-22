from flask import Flask, jsonify, request
from .models import Order, OrderItem
from .store import save_order, get_order, get_all_orders
from .errors import APIError, problem_response
from .gateway import check_item
import uuid


app = Flask(__name__)

idempotency_store = {}


@app.errorhandler(APIError)
def handle_api_error(error):
    return jsonify(problem_response(error)), error.status


@app.post("/orders")
def create_order():
    idempotency_key = request.headers.get("Idempotency-Key")

    if not idempotency_key:
        raise APIError(
            422,
            "Invalid request",
            "Idempotency-Key header is required."
        )

    if idempotency_key in idempotency_store:
        return jsonify(idempotency_store[idempotency_key]), 200

    data = request.get_json(silent=True)

    if not data:
        raise APIError(
            422,
            "Invalid request",
            "Request body is required."
        )

    required = ["student_id", "restaurant_id", "items"]

    for field in required:
        if field not in data:
            raise APIError(
                422,
                "Invalid request",
                f"Missing field: {field}"
            )

    if not isinstance(data["student_id"], str) or not data["student_id"].strip():
        raise APIError(
            422,
            "Invalid request",
            "student_id must be a non-empty string."
        )

    if not isinstance(data["restaurant_id"], str) or not data["restaurant_id"].strip():
        raise APIError(
            422,
            "Invalid request",
            "restaurant_id must be a non-empty string."
        )

    if not isinstance(data["items"], list) or len(data["items"]) == 0:
        raise APIError(
            422,
            "Invalid request",
            "Items must be a non-empty list."
        )

    items = []

    for item in data["items"]:

        if not isinstance(item, dict):
            raise APIError(
                422,
                "Invalid request",
                "Each item must be an object."
            )

        if "item_id" not in item or "quantity" not in item:
            raise APIError(
                422,
                "Invalid request",
                "Each item must contain item_id and quantity."
            )

        if not isinstance(item["item_id"], str) or not item["item_id"].strip():
            raise APIError(
                422,
                "Invalid request",
                "item_id must be a non-empty string."
            )

        if (
            not isinstance(item["quantity"], int)
            or isinstance(item["quantity"], bool)
            or item["quantity"] < 1
        ):
            raise APIError(
                422,
                "Invalid request",
                "Quantity must be a positive integer."
            )

        # Call the CampusEats Catalog service.
        # If it is unavailable, continue using fallback mode.
        item_info = check_item(item["item_id"])

        if item_info is None:
            print(
                f"Catalog service unavailable for {item['item_id']}. "
                "Using fallback mode."
            )

        items.append(
            OrderItem(
                item_id=item["item_id"],
                quantity=item["quantity"]
            )
        )

    order = Order(
        order_id=str(uuid.uuid4()),
        student_id=data["student_id"],
        restaurant_id=data["restaurant_id"],
        items=items
    )

    save_order(order)

    response_data = order_to_dict(order)

    idempotency_store[idempotency_key] = response_data

    response = jsonify(response_data)
    response.status_code = 201
    response.headers["Location"] = f"/orders/{order.order_id}"

    return response


@app.get("/orders")
def list_orders():
    student_id = request.args.get("student_id")

    if student_id is not None and not student_id.strip():
        raise APIError(
            422,
            "Invalid request",
            "student_id cannot be empty."
        )

    orders = get_all_orders()

    if student_id:
        orders = [
            order
            for order in orders
            if order.student_id == student_id
        ]

    return jsonify(
        [order_to_dict(order) for order in orders]
    ), 200


@app.get("/orders/<order_id>")
def get_order_by_id(order_id):
    order = get_order(order_id)

    if not order:
        raise APIError(
            404,
            "Order not found",
            "The requested order does not exist."
        )

    return jsonify(order_to_dict(order)), 200


@app.patch("/orders/<order_id>")
def update_order(order_id):
    order = get_order(order_id)

    if not order:
        raise APIError(
            404,
            "Order not found",
            "The requested order does not exist."
        )

    data = request.get_json(silent=True)

    if not data or "status" not in data:
        raise APIError(
            422,
            "Invalid request",
            "Status is required."
        )

    allowed_statuses = [
        "pending",
        "confirmed",
        "preparing",
        "ready",
        "delivered",
        "cancelled"
    ]

    new_status = data["status"]

    if new_status not in allowed_statuses:
        raise APIError(
            422,
            "Invalid request",
            "Invalid order status."
        )

    valid_transitions = {
        "pending": ["confirmed", "cancelled"],
        "confirmed": ["preparing", "cancelled"],
        "preparing": ["ready"],
        "ready": ["delivered"],
        "delivered": [],
        "cancelled": []
    }

    if new_status == order.status:
        return jsonify(order_to_dict(order)), 200

    if new_status not in valid_transitions[order.status]:
        raise APIError(
            409,
            "Invalid state transition",
            f"Order cannot change from {order.status} to {new_status}."
        )

    order.status = new_status

    return jsonify(order_to_dict(order)), 200


@app.post("/orders/<order_id>/cancellation")
def cancel_order(order_id):
    order = get_order(order_id)

    if not order:
        raise APIError(
            404,
            "Order not found",
            "The requested order does not exist."
        )

    if order.status in ["delivered", "cancelled"]:
        raise APIError(
            409,
            "Order cannot be cancelled",
            "The order is already delivered or cancelled."
        )

    order.status = "cancelled"

    return "", 202


def order_to_dict(order):
    return {
        "order_id": order.order_id,
        "student_id": order.student_id,
        "restaurant_id": order.restaurant_id,
        "items": [
            {
                "item_id": item.item_id,
                "quantity": item.quantity
            }
            for item in order.items
        ],
        "status": order.status,
        "total": order.total
    }


if __name__ == "__main__":
    app.run(debug=True, port=8000)