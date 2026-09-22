from service import app as app_module
from service.app import app


AUTH = {"Authorization": "Bearer test-token"}


def make_order(client, idem_key, token="test-token", student_id="S001"):
    response = client.post(
        "/orders",
        headers={"Idempotency-Key": idem_key, "Authorization": f"Bearer {token}"},
        json={
            "student_id": student_id,
            "restaurant_id": "R001",
            "items": [{"item_id": "I001", "quantity": 2}],
        },
    )
    return response


# --- Assignment 4 behavior, preserved (Authorization header now required) -------

def test_create_order():
    client = app.test_client()
    response = make_order(client, "test-key-001", token="tok-create")

    assert response.status_code == 201
    assert "order_id" in response.json
    assert response.headers.get("Location") == f"/orders/{response.json['order_id']}"


def test_get_missing_order():
    client = app.test_client()
    response = client.get("/orders/does-not-exist")
    assert response.status_code == 404


def test_invalid_order():
    client = app.test_client()
    response = client.post(
        "/orders",
        headers={"Idempotency-Key": "test-key-002", "Authorization": "Bearer tok-invalid"},
        json={"student_id": "S001"},
    )
    assert response.status_code == 422


def test_idempotency():
    client = app.test_client()
    order_data = {
        "student_id": "S002",
        "restaurant_id": "R001",
        "items": [{"item_id": "I001", "quantity": 1}],
    }
    headers = {"Idempotency-Key": "unique-key-001", "Authorization": "Bearer tok-idem"}

    first_response = client.post("/orders", headers=headers, json=order_data)
    second_response = client.post("/orders", headers=headers, json=order_data)

    assert first_response.status_code == 201
    assert second_response.status_code == 200
    assert first_response.json["order_id"] == second_response.json["order_id"]


def test_cancellation_conflict_when_already_cancelled():
    client = app.test_client()
    create = make_order(client, "cancel-key-001", token="tok-cancel")
    order_id = create.json["order_id"]

    first_cancel = client.post(f"/orders/{order_id}/cancellation", headers={"Authorization": "Bearer tok-cancel"})
    second_cancel = client.post(f"/orders/{order_id}/cancellation", headers={"Authorization": "Bearer tok-cancel"})

    assert first_cancel.status_code == 202
    assert second_cancel.status_code == 409


def test_patch_invalid_state_transition():
    client = app.test_client()
    create = make_order(client, "patch-conflict-key", token="tok-patchconflict")
    order_id = create.json["order_id"]

    response = client.patch(
        f"/orders/{order_id}",
        headers={"Authorization": "Bearer tok-patchconflict"},
        json={"status": "delivered"},
    )
    assert response.status_code == 409


# --- Assignment 5: Part A - methods --------------------------------------------

def test_write_endpoints_require_authorization():
    client = app.test_client()

    create_response = client.post(
        "/orders",
        headers={"Idempotency-Key": "no-auth-key"},
        json={"student_id": "S001", "restaurant_id": "R001", "items": [{"item_id": "I001", "quantity": 1}]},
    )
    assert create_response.status_code == 401

    empty_bearer_response = client.post(
        "/orders",
        headers={"Idempotency-Key": "empty-auth-key", "Authorization": "Bearer "},
        json={"student_id": "S001", "restaurant_id": "R001", "items": [{"item_id": "I001", "quantity": 1}]},
    )
    assert empty_bearer_response.status_code == 401


def test_options_returns_allow_header():
    client = app.test_client()
    create = make_order(client, "options-key", token="tok-options")
    order_id = create.json["order_id"]

    response = client.open(f"/orders/{order_id}", method="OPTIONS")

    assert response.status_code == 200
    allow = response.headers.get("Allow", "")
    assert "GET" in allow
    assert "PATCH" in allow


def test_method_override_lets_post_act_as_patch():
    client = app.test_client()
    create = make_order(client, "override-key", token="tok-override")
    order_id = create.json["order_id"]

    response = client.post(
        f"/orders/{order_id}",
        headers={"Authorization": "Bearer tok-override", "X-HTTP-Method-Override": "PATCH"},
        json={"status": "confirmed"},
    )

    assert response.status_code == 200
    assert response.json["status"] == "confirmed"


def test_list_orders_supports_sort_and_pagination():
    client = app.test_client()
    make_order(client, "sort-key-a", token="tok-sort-a", student_id="S_A")
    make_order(client, "sort-key-b", token="tok-sort-b", student_id="S_B")

    response = client.get("/orders?sort=student_id&order=desc&limit=1")
    assert response.status_code == 200
    assert len(response.json) == 1

    invalid_sort = client.get("/orders?sort=not_a_field")
    assert invalid_sort.status_code == 422


# --- Assignment 5: Part B - headers ---------------------------------------------

def test_406_when_accept_header_unsupported():
    client = app.test_client()
    response = client.get("/orders", headers={"Accept": "text/xml"})
    assert response.status_code == 406


def test_malformed_json_returns_400_not_422():
    client = app.test_client()
    response = client.post(
        "/orders",
        headers={
            "Idempotency-Key": "malformed-key",
            "Authorization": "Bearer tok-malformed",
            "Content-Type": "application/json",
        },
        data="{not valid json",
    )
    assert response.status_code == 400

    domain_error_response = client.post(
        "/orders",
        headers={"Idempotency-Key": "domain-key", "Authorization": "Bearer tok-malformed2"},
        json={"student_id": "S001"},
    )
    assert domain_error_response.status_code == 422


def test_cors_preflight_headers():
    client = app.test_client()
    response = client.open(
        "/orders",
        method="OPTIONS",
        headers={"Access-Control-Request-Method": "POST", "Origin": "http://example.com"},
    )
    assert response.status_code == 200
    assert response.headers.get("Access-Control-Allow-Origin") == "*"
    assert "POST" in response.headers.get("Access-Control-Allow-Methods", "")
    assert "Authorization" in response.headers.get("Access-Control-Allow-Headers", "")


def test_security_headers_present_on_every_response():
    client = app.test_client()
    response = client.get("/orders/does-not-exist")
    assert response.headers.get("X-Content-Type-Options") == "nosniff"
    assert "Strict-Transport-Security" in response.headers


def test_rate_limit_returns_429_with_retry_after():
    client = app.test_client()

    original_max = app_module.RATE_LIMIT_MAX
    app_module.RATE_LIMIT_MAX = 2
    try:
        headers = {"Authorization": "Bearer tok-ratelimit"}
        r1 = client.get("/orders/does-not-exist", headers=headers)  # GET, not rate-limited
        r2 = make_order(client, "rl-key-1", token="tok-ratelimit")
        r3 = make_order(client, "rl-key-2", token="tok-ratelimit")
        r4 = make_order(client, "rl-key-3", token="tok-ratelimit")

        assert r2.status_code == 201
        assert r3.status_code == 201
        assert r4.status_code == 429
        assert "Retry-After" in r4.headers
        assert r4.headers.get("X-RateLimit-Remaining") == "0"
    finally:
        app_module.RATE_LIMIT_MAX = original_max


# --- Assignment 5: Part C - caching & safe retries -------------------------------

def test_conditional_get_returns_304_when_etag_matches():
    client = app.test_client()
    create = make_order(client, "etag-key", token="tok-etag")
    order_id = create.json["order_id"]

    first_get = client.get(f"/orders/{order_id}")
    assert first_get.status_code == 200
    etag = first_get.headers.get("ETag")
    assert etag

    conditional_get = client.get(f"/orders/{order_id}", headers={"If-None-Match": etag})
    assert conditional_get.status_code == 304
    assert conditional_get.data == b""


def test_conditional_write_returns_412_on_stale_etag():
    client = app.test_client()
    create = make_order(client, "match-key", token="tok-match")
    order_id = create.json["order_id"]

    stale_patch = client.patch(
        f"/orders/{order_id}",
        headers={"Authorization": "Bearer tok-match", "If-Match": '"stale-value"'},
        json={"status": "confirmed"},
    )
    assert stale_patch.status_code == 412

    fresh_get = client.get(f"/orders/{order_id}")
    current_etag = fresh_get.headers.get("ETag")

    good_patch = client.patch(
        f"/orders/{order_id}",
        headers={"Authorization": "Bearer tok-match", "If-Match": current_etag},
        json={"status": "confirmed"},
    )
    assert good_patch.status_code == 200


def test_idempotency_key_prevents_duplicate_order():
    client = app.test_client()
    first = make_order(client, "dup-check-key", token="tok-dup")
    second = make_order(client, "dup-check-key", token="tok-dup")

    assert first.status_code == 201
    assert second.status_code == 200
    assert first.json["order_id"] == second.json["order_id"]
