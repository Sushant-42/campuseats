import functools
import gzip
import hashlib
import json
import time
import uuid

from flask import Flask, g, jsonify, request

from .errors import APIError, problem_response
from .gateway import check_item
from .models import Order, OrderItem
from .store import get_all_orders, get_order, save_order

app = Flask(__name__)

idempotency_store = {}

# --- Assignment 5 configuration -------------------------------------------------

# Per-client rate limit (client = Authorization bearer token). Kept small on
# purpose so the limit can be demonstrated with a handful of curl calls.
RATE_LIMIT_MAX = 5
RATE_LIMIT_WINDOW_SECONDS = 60

# In-memory bucket: {client_key: [timestamp, timestamp, ...]}
_rate_limit_buckets = {}

ALLOWED_STATUSES = [
    "pending",
    "confirmed",
    "preparing",
    "ready",
    "delivered",
    "cancelled",
]

VALID_TRANSITIONS = {
    "pending": ["confirmed", "cancelled"],
    "confirmed": ["preparing", "cancelled"],
    "preparing": ["ready"],
    "ready": ["delivered"],
    "delivered": [],
    "cancelled": [],
}

SORTABLE_FIELDS = ["student_id", "restaurant_id", "status"]

CORS_ALLOWED_HEADERS = (
    "Content-Type, Authorization, Idempotency-Key, If-Match, "
    "If-None-Match, X-HTTP-Method-Override"
)


# --- WSGI-level X-HTTP-Method-Override middleware --------------------------------
#
# Documented fallback ONLY: a constrained client that cannot send PATCH/PUT/DELETE
# may send a POST with an X-HTTP-Method-Override header naming the method it
# really wants. The override happens at the WSGI layer, before routing, so the
# normal PATCH/DELETE view functions run unchanged.

class MethodOverrideMiddleware:
    def __init__(self, wrapped_app):
        self.wrapped_app = wrapped_app

    def __call__(self, environ, start_response):
        override = environ.get("HTTP_X_HTTP_METHOD_OVERRIDE")
        if override and environ.get("REQUEST_METHOD", "").upper() == "POST":
            environ["REQUEST_METHOD"] = override.strip().upper()
        return self.wrapped_app(environ, start_response)


app.wsgi_app = MethodOverrideMiddleware(app.wsgi_app)


# --- Error handling ---------------------------------------------------------------

@app.errorhandler(APIError)
def handle_api_error(error):
    response = jsonify(problem_response(error))
    response.status_code = error.status
    if error.status == 429 and error.retry_after is not None:
        response.headers["Retry-After"] = str(error.retry_after)
    return response


# --- Shared helpers -----------------------------------------------------------

def order_to_dict(order):
    return {
        "order_id": order.order_id,
        "student_id": order.student_id,
        "restaurant_id": order.restaurant_id,
        "items": [
            {"item_id": item.item_id, "quantity": item.quantity}
            for item in order.items
        ],
        "status": order.status,
        "total": order.total,
    }


def compute_etag(order):
    """ETag derived from the order's current state. Changes automatically
    whenever anything about the order (e.g. status) changes."""
    payload = json.dumps(order_to_dict(order), sort_keys=True)
    digest = hashlib.md5(payload.encode("utf-8")).hexdigest()
    return f'"{digest}"'


def parse_json_body():
    """Distinguishes a malformed request (400) from a request that is valid
    JSON but fails domain validation (422)."""
    raw = request.get_data()

    if not raw or not raw.strip():
        raise APIError(400, "Malformed request", "Request body is required and must be valid JSON.")

    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise APIError(400, "Malformed request", "Request body is not valid JSON.")

    if not isinstance(data, dict):
        raise APIError(400, "Malformed request", "Request body must be a JSON object.")

    return data


def get_bearer_token():
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        token = auth[len("Bearer "):].strip()
        return token or None
    return None


def check_rate_limit(client_key):
    """Sliding-window rate limit, per client key. Returns
    (allowed, remaining, retry_after_seconds)."""
    now = time.time()
    window_start = now - RATE_LIMIT_WINDOW_SECONDS

    bucket = [ts for ts in _rate_limit_buckets.get(client_key, []) if ts > window_start]

    if len(bucket) >= RATE_LIMIT_MAX:
        oldest = min(bucket)
        retry_after = max(1, int(RATE_LIMIT_WINDOW_SECONDS - (now - oldest)))
        _rate_limit_buckets[client_key] = bucket
        return False, 0, retry_after

    bucket.append(now)
    _rate_limit_buckets[client_key] = bucket
    remaining = RATE_LIMIT_MAX - len(bucket)
    return True, remaining, 0


def require_auth(view):
    """Protects state-changing endpoints: requires Authorization: Bearer <token>
    and enforces the per-client rate limit. Header handling only - there is no
    real token/user system behind it."""

    @functools.wraps(view)
    def wrapper(*args, **kwargs):
        token = get_bearer_token()

        if not token:
            raise APIError(401, "Unauthorized", "A valid Authorization: Bearer <token> header is required.")

        allowed, remaining, retry_after = check_rate_limit(token)
        g.rate_limit_limit = RATE_LIMIT_MAX
        g.rate_limit_remaining = remaining if allowed else 0

        if not allowed:
            raise APIError(
                429,
                "Too Many Requests",
                "Rate limit exceeded for this client.",
                retry_after=retry_after,
            )

        return view(*args, **kwargs)

    return wrapper


def acceptable_json(accept_header):
    if not accept_header or not accept_header.strip():
        return True
    accept_header = accept_header.lower()
    return (
        "application/json" in accept_header
        or "*/*" in accept_header
        or "application/*" in accept_header
    )


# --- Global request/response hooks --------------------------------------------

@app.before_request
def negotiate_content_type():
    if request.method == "OPTIONS":
        return None

    if not acceptable_json(request.headers.get("Accept")):
        body = {
            "type": "about:blank",
            "title": "Not Acceptable",
            "status": 406,
            "detail": "This API only produces application/json.",
        }
        response = jsonify(body)
        response.status_code = 406
        return response

    return None


@app.after_request
def add_common_headers(response):
    # B7: security & general headers
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"

    # B6: CORS - allow any origin to read this API, and answer preflights
    response.headers["Access-Control-Allow-Origin"] = "*"
    if request.method == "OPTIONS":
        allow = response.headers.get("Allow", "")
        response.headers["Access-Control-Allow-Methods"] = allow or "GET, POST, PATCH, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = CORS_ALLOWED_HEADERS

    # B5: rate-limit signalling (only set on protected endpoints that ran require_auth)
    if hasattr(g, "rate_limit_limit"):
        response.headers["X-RateLimit-Limit"] = str(g.rate_limit_limit)
        response.headers["X-RateLimit-Remaining"] = str(g.rate_limit_remaining)

    # B1: gzip large JSON bodies when the client says it can accept it
    accept_encoding = request.headers.get("Accept-Encoding", "")
    if (
        "gzip" in accept_encoding.lower()
        and response.content_length
        and response.content_length > 500
        and "Content-Encoding" not in response.headers
    ):
        compressed = gzip.compress(response.get_data())
        response.set_data(compressed)
        response.headers["Content-Encoding"] = "gzip"
        response.headers["Content-Length"] = str(len(compressed))
        existing_vary = response.headers.get("Vary")
        response.headers["Vary"] = f"{existing_vary}, Accept-Encoding" if existing_vary else "Accept-Encoding"

    return response


# --- /orders ------------------------------------------------------------------

@app.post("/orders")
@require_auth
def create_order():
    idempotency_key = request.headers.get("Idempotency-Key")

    if not idempotency_key:
        raise APIError(422, "Invalid request", "Idempotency-Key header is required.")

    if idempotency_key in idempotency_store:
        response = jsonify(idempotency_store[idempotency_key])
        response.status_code = 200
        response.headers["Cache-Control"] = "no-store"
        return response

    data = parse_json_body()

    required = ["student_id", "restaurant_id", "items"]
    for field in required:
        if field not in data:
            raise APIError(422, "Invalid request", f"Missing field: {field}")

    if not isinstance(data["student_id"], str) or not data["student_id"].strip():
        raise APIError(422, "Invalid request", "student_id must be a non-empty string.")

    if not isinstance(data["restaurant_id"], str) or not data["restaurant_id"].strip():
        raise APIError(422, "Invalid request", "restaurant_id must be a non-empty string.")

    if not isinstance(data["items"], list) or len(data["items"]) == 0:
        raise APIError(422, "Invalid request", "Items must be a non-empty list.")

    items = []

    for item in data["items"]:
        if not isinstance(item, dict):
            raise APIError(422, "Invalid request", "Each item must be an object.")

        if "item_id" not in item or "quantity" not in item:
            raise APIError(422, "Invalid request", "Each item must contain item_id and quantity.")

        if not isinstance(item["item_id"], str) or not item["item_id"].strip():
            raise APIError(422, "Invalid request", "item_id must be a non-empty string.")

        if (
            not isinstance(item["quantity"], int)
            or isinstance(item["quantity"], bool)
            or item["quantity"] < 1
        ):
            raise APIError(422, "Invalid request", "Quantity must be a positive integer.")

        # Call the CampusEats Catalog service.
        # If it is unavailable, continue using fallback mode.
        item_info = check_item(item["item_id"])

        if item_info is None:
            print(f"Catalog service unavailable for {item['item_id']}. Using fallback mode.")

        items.append(OrderItem(item_id=item["item_id"], quantity=item["quantity"]))

    order = Order(
        order_id=str(uuid.uuid4()),
        student_id=data["student_id"],
        restaurant_id=data["restaurant_id"],
        items=items,
    )

    save_order(order)

    response_data = order_to_dict(order)
    idempotency_store[idempotency_key] = response_data

    response = jsonify(response_data)
    response.status_code = 201
    response.headers["Location"] = f"/orders/{order.order_id}"
    response.headers["Cache-Control"] = "no-store"

    return response


@app.get("/orders")
def list_orders():
    student_id = request.args.get("student_id")
    sort_field = request.args.get("sort")
    order_dir = request.args.get("order", "asc")
    limit_raw = request.args.get("limit")
    offset_raw = request.args.get("offset")

    if student_id is not None and not student_id.strip():
        raise APIError(422, "Invalid request", "student_id cannot be empty.")

    if sort_field is not None and sort_field not in SORTABLE_FIELDS:
        raise APIError(422, "Invalid request", f"sort must be one of {SORTABLE_FIELDS}.")

    if order_dir not in ("asc", "desc"):
        raise APIError(422, "Invalid request", "order must be 'asc' or 'desc'.")

    limit = None
    if limit_raw is not None:
        if not limit_raw.isdigit() or int(limit_raw) < 1:
            raise APIError(422, "Invalid request", "limit must be a positive integer.")
        limit = int(limit_raw)

    offset = 0
    if offset_raw is not None:
        if not offset_raw.isdigit():
            raise APIError(422, "Invalid request", "offset must be a non-negative integer.")
        offset = int(offset_raw)

    orders = get_all_orders()

    if student_id:
        orders = [order for order in orders if order.student_id == student_id]

    if sort_field:
        orders = sorted(
            orders,
            key=lambda o: getattr(o, sort_field),
            reverse=(order_dir == "desc"),
        )

    orders = orders[offset:]
    if limit is not None:
        orders = orders[:limit]

    return jsonify([order_to_dict(order) for order in orders]), 200


# --- /orders/<order_id> --------------------------------------------------------

@app.get("/orders/<order_id>")
def get_order_by_id(order_id):
    order = get_order(order_id)

    if not order:
        raise APIError(404, "Order not found", "The requested order does not exist.")

    etag = compute_etag(order)

    if request.headers.get("If-None-Match") == etag:
        response = app.response_class(status=304)
        response.headers["ETag"] = etag
        response.headers["Cache-Control"] = "private, max-age=30"
        return response

    response = jsonify(order_to_dict(order))
    response.status_code = 200
    response.headers["ETag"] = etag
    response.headers["Cache-Control"] = "private, max-age=30"
    return response


@app.patch("/orders/<order_id>")
@require_auth
def update_order(order_id):
    order = get_order(order_id)

    if not order:
        raise APIError(404, "Order not found", "The requested order does not exist.")

    if_match = request.headers.get("If-Match")
    if if_match is not None:
        current_etag = compute_etag(order)
        if if_match != current_etag:
            raise APIError(
                412,
                "Precondition Failed",
                "The order has changed since you last read it. Re-fetch and retry.",
            )

    data = parse_json_body()

    if "status" not in data:
        raise APIError(422, "Invalid request", "Status is required.")

    new_status = data["status"]

    if new_status not in ALLOWED_STATUSES:
        raise APIError(422, "Invalid request", "Invalid order status.")

    if new_status == order.status:
        response = jsonify(order_to_dict(order))
        response.status_code = 200
        response.headers["ETag"] = compute_etag(order)
        response.headers["Cache-Control"] = "no-store"
        return response

    if new_status not in VALID_TRANSITIONS[order.status]:
        raise APIError(
            409,
            "Invalid state transition",
            f"Order cannot change from {order.status} to {new_status}.",
        )

    order.status = new_status

    response = jsonify(order_to_dict(order))
    response.status_code = 200
    response.headers["ETag"] = compute_etag(order)
    response.headers["Cache-Control"] = "no-store"
    return response


@app.post("/orders/<order_id>/cancellation")
@require_auth
def cancel_order(order_id):
    order = get_order(order_id)

    if not order:
        raise APIError(404, "Order not found", "The requested order does not exist.")

    if order.status in ["delivered", "cancelled"]:
        raise APIError(409, "Order cannot be cancelled", "The order is already delivered or cancelled.")

    order.status = "cancelled"

    return "", 202


if __name__ == "__main__":
    app.run(debug=True, port=8000)
