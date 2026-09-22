"""
Drives real HTTP requests (via curl) against the locally running service and
writes curl-transcript.txt. No responses in that file are fabricated - every
line under "ACTUAL OUTPUT" is copied verbatim from a subprocess.run(["curl", ...])
call made while service/app.py was actually running on localhost:8000.
"""
import json
import re
import subprocess

BASE = "http://localhost:8000"
OUT_PATH = "curl-transcript.txt"

sections = []


def curl(args, label, command_str):
    result = subprocess.run(["curl", "-v", "-sS"] + args, capture_output=True, text=True)
    output = result.stdout.strip()
    sections.append((label, command_str, output))
    return output


def extract_header(raw_response, header_name):
    for line in raw_response.splitlines():
        if line.lower().startswith(header_name.lower() + ":"):
            return line.split(":", 1)[1].strip()
    return None


def extract_json(raw_response):
    body = raw_response.split("\r\n\r\n", 1)
    if len(body) < 2:
        body = raw_response.split("\n\n", 1)
    try:
        return json.loads(body[1])
    except Exception:
        return None


# 1. Successful create - 201 + Location
resp = curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-create",
        "-H", "Idempotency-Key: demo-create-1",
        "--data-raw", '{"student_id":"S100","restaurant_id":"R100","items":[{"item_id":"I001","quantity":2}]}',
    ],
    "1. Successful order creation - 201 Created + Location + rate-limit headers",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-create" -H "Idempotency-Key: demo-create-1" '
    '--data-raw \'{"student_id":"S100","restaurant_id":"R100","items":[{"item_id":"I001","quantity":2}]}\'',
)
order_id = extract_json(resp)["order_id"]

# 2. Idempotency-Key repeated -> 200, same body, no duplicate
curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-create",
        "-H", "Idempotency-Key: demo-create-1",
        "--data-raw", '{"student_id":"S100","restaurant_id":"R100","items":[{"item_id":"I001","quantity":2}]}',
    ],
    "2. Idempotency-Key repeated - same key returns original order, 200 (no duplicate)",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-create" -H "Idempotency-Key: demo-create-1" '
    '--data-raw \'{"student_id":"S100","restaurant_id":"R100","items":[{"item_id":"I001","quantity":2}]}\' '
    '(same body + same Idempotency-Key as step 1)',
)

# 3. Malformed JSON -> 400
curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-malformed",
        "-H", "Idempotency-Key: demo-bad-json",
        "-d", "{bad json",
    ],
    "3. Malformed JSON body - 400 Bad Request",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-malformed" -H "Idempotency-Key: demo-bad-json" -d "{bad json"',
)

# 4. Valid JSON, domain validation failure -> 422
curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-422",
        "-H", "Idempotency-Key: demo-422",
        "--data-raw", '{"student_id":"S100"}',
    ],
    "4. Domain validation failure (valid JSON, missing fields) - 422 Unprocessable Entity",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-422" -H "Idempotency-Key: demo-422" '
    '--data-raw \'{"student_id":"S100"}\'',
)

# 5. Missing Authorization -> 401
curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Idempotency-Key: demo-401",
        "--data-raw", '{"student_id":"S1","restaurant_id":"R1","items":[{"item_id":"I1","quantity":1}]}',
    ],
    "5. Missing Authorization header - 401 Unauthorized",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Idempotency-Key: demo-401" '
    '--data-raw \'{"student_id":"S1","restaurant_id":"R1","items":[{"item_id":"I1","quantity":1}]}\'',
)

# 6. Missing resource -> 404
curl(
    [f"{BASE}/orders/does-not-exist"],
    "6. Missing resource - 404 Not Found",
    "curl -v -sS $BASE/orders/does-not-exist",
)

# 7. GET single order -> 200 + ETag + Cache-Control
resp = curl(
    [f"{BASE}/orders/{order_id}"],
    "7. GET single order - 200 with ETag + Cache-Control",
    "curl -v -sS $BASE/orders/{order_id}".format(order_id=order_id),
)
etag = extract_header(resp, "ETag")

# 8. Conditional GET, matching If-None-Match -> 304
curl(
    [f"{BASE}/orders/{order_id}", "-H", f"If-None-Match: {etag}"],
    "8. Conditional GET with matching If-None-Match - 304 Not Modified",
    f'curl -v -sS $BASE/orders/{order_id} -H \'If-None-Match: {etag}\'',
)

# 9. Conditional write, stale If-Match -> 412
curl(
    [
        "-X", "PATCH", f"{BASE}/orders/{order_id}",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-write",
        "-H", 'If-Match: "stale-etag-value"',
        "--data-raw", '{"status":"confirmed"}',
    ],
    "9. Conditional write with stale If-Match - 412 Precondition Failed",
    f'curl -v -sS -X PATCH $BASE/orders/{order_id} -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-write" -H \'If-Match: "stale-etag-value"\' '
    '--data-raw \'{"status":"confirmed"}\'',
)

# 10. Conditional write, correct If-Match -> 200, ETag changes
curl(
    [
        "-X", "PATCH", f"{BASE}/orders/{order_id}",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-write",
        "-H", f"If-Match: {etag}",
        "--data-raw", '{"status":"confirmed"}',
    ],
    "10. Conditional write with correct If-Match - 200 OK (order moves pending -> confirmed, ETag changes)",
    f'curl -v -sS -X PATCH $BASE/orders/{order_id} -H "Content-Type: application/json" '
    f'-H "Authorization: Bearer tok-write" -H \'If-Match: {etag}\' '
    '--data-raw \'{"status":"confirmed"}\'',
)

# 11. Invalid state transition -> 409 (separate order so it doesn't collide with the flow above)
resp = curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-conflict",
        "-H", "Idempotency-Key: demo-conflict-order",
        "--data-raw", '{"student_id":"S200","restaurant_id":"R200","items":[{"item_id":"I001","quantity":1}]}',
    ],
    "11a. (setup) create a fresh pending order for the 409 demo",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-conflict" -H "Idempotency-Key: demo-conflict-order" '
    '--data-raw \'{"student_id":"S200","restaurant_id":"R200","items":[{"item_id":"I001","quantity":1}]}\'',
)
conflict_order_id = extract_json(resp)["order_id"]

curl(
    [
        "-X", "PATCH", f"{BASE}/orders/{conflict_order_id}",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-conflict",
        "--data-raw", '{"status":"delivered"}',
    ],
    "11b. Invalid state transition (pending -> delivered) - 409 Conflict",
    f'curl -v -sS -X PATCH $BASE/orders/{conflict_order_id} -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-conflict" --data-raw \'{"status":"delivered"}\'',
)

# 12. OPTIONS on a single resource -> Allow header
curl(
    ["-X", "OPTIONS", f"{BASE}/orders/{order_id}"],
    "12. OPTIONS on a single resource - Allow header lists its methods",
    f"curl -v -sS -X OPTIONS $BASE/orders/{order_id}",
)

# 13. CORS preflight on the collection
curl(
    [
        "-X", "OPTIONS", f"{BASE}/orders",
        "-H", "Origin: http://example.com",
        "-H", "Access-Control-Request-Method: POST",
    ],
    "13. CORS preflight on the collection resource",
    'curl -v -sS -X OPTIONS $BASE/orders -H "Origin: http://example.com" '
    '-H "Access-Control-Request-Method: POST"',
)

# 14. Unsupported Accept header -> 406
curl(
    [f"{BASE}/orders", "-H", "Accept: text/xml"],
    "14. Unsupported Accept header - 406 Not Acceptable",
    'curl -v -sS $BASE/orders -H "Accept: text/xml"',
)

# 15. X-HTTP-Method-Override: POST treated as PATCH
resp = curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-override",
        "-H", "Idempotency-Key: demo-override-order",
        "--data-raw", '{"student_id":"S300","restaurant_id":"R300","items":[{"item_id":"I001","quantity":1}]}',
    ],
    "15a. (setup) create a fresh order for the method-override demo",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-override" -H "Idempotency-Key: demo-override-order" '
    '--data-raw \'{"student_id":"S300","restaurant_id":"R300","items":[{"item_id":"I001","quantity":1}]}\'',
)
override_order_id = extract_json(resp)["order_id"]

curl(
    [
        "-X", "POST", f"{BASE}/orders/{override_order_id}",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-override",
        "-H", "X-HTTP-Method-Override: PATCH",
        "--data-raw", '{"status":"confirmed"}',
    ],
    "15b. X-HTTP-Method-Override - a POST is treated as PATCH",
    f'curl -v -sS -X POST $BASE/orders/{override_order_id} -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-override" -H "X-HTTP-Method-Override: PATCH" '
    '--data-raw \'{"status":"confirmed"}\'',
)

# 16. Rate limit: dedicated fresh token, loop past the default limit of 5/60s
resp = curl(
    [
        "-X", "POST", f"{BASE}/orders",
        "-H", "Content-Type: application/json",
        "-H", "Authorization: Bearer tok-setup-for-ratelimit",
        "-H", "Idempotency-Key: demo-ratelimit-order",
        "--data-raw", '{"student_id":"S400","restaurant_id":"R400","items":[{"item_id":"I001","quantity":1}]}',
    ],
    "16a. (setup) create a fresh order for the rate-limit demo",
    'curl -v -sS -X POST $BASE/orders -H "Content-Type: application/json" '
    '-H "Authorization: Bearer tok-setup-for-ratelimit" -H "Idempotency-Key: demo-ratelimit-order" '
    '--data-raw \'{"student_id":"S400","restaurant_id":"R400","items":[{"item_id":"I001","quantity":1}]}\'',
)
ratelimit_order_id = extract_json(resp)["order_id"]

rl_lines = [
    "16b. Rate limit exceeded - 6 calls with the SAME fresh Bearer token against the",
    "     default per-client budget of 5 requests / 60 seconds -> the 6th gets 429 + Retry-After",
    "",
    "COMMAND (repeated 6 times, same token):",
    f'curl -v -sS -X POST $BASE/orders/{ratelimit_order_id}/cancellation '
    '-H "Authorization: Bearer tok-ratelimit-demo"',
    "",
    "ACTUAL OUTPUT (status line + rate-limit headers for each call):",
]
for i in range(1, 7):
    result = subprocess.run(
        [
            "curl", "-v", "-sS", "-X", "POST",
            f"{BASE}/orders/{ratelimit_order_id}/cancellation",
            "-H", "Authorization: Bearer tok-ratelimit-demo",
        ],
        capture_output=True, text=True,
    )
    raw = result.stdout
    status_line = raw.splitlines()[0] if raw.splitlines() else ""
    limit = extract_header(raw, "X-RateLimit-Limit")
    remaining = extract_header(raw, "X-RateLimit-Remaining")
    retry_after = extract_header(raw, "Retry-After")
    rl_lines.append(f"--- call {i} ---")
    rl_lines.append(status_line)
    if limit:
        rl_lines.append(f"X-RateLimit-Limit: {limit}")
    if remaining:
        rl_lines.append(f"X-RateLimit-Remaining: {remaining}")
    if retry_after:
        rl_lines.append(f"Retry-After: {retry_after}")

sections.append(("__raw__", None, "\n".join(rl_lines)))

# Write transcript
with open(OUT_PATH, "w") as f:
    f.write("=" * 60 + "\n")
    f.write("CampusEats Orders REST Service - Assignment 5 curl Evidence Transcript\n")
    f.write("=" * 60 + "\n\n")
    f.write("Team ID: 5\n")
    f.write("Sushant Prashant Prabhavalakar - 20251651093\n")
    f.write("Harsh Yadav - 20251651042\n\n")
    f.write("Service: CampusEats Orders REST Service\n")
    f.write("Base URL: http://localhost:8000\n\n")
    f.write(
        "This transcript was produced by running service/app.py locally and\n"
        "firing real curl requests at it (see make_transcript.py). Nothing below\n"
        "is a hand-written/expected response - it is the literal output of each\n"
        "curl call, captured at the time this file was generated.\n"
    )

    for label, command, output in sections:
        f.write("\n" + "=" * 60 + "\n")
        if label != "__raw__":
            f.write(label + "\n")
            f.write("=" * 60 + "\n\n")
            f.write("COMMAND:\n\n")
            f.write(command + "\n\n")
            f.write("ACTUAL OUTPUT:\n\n")
            f.write(output + "\n")
        else:
            f.write(output + "\n")

    f.write("\n" + "=" * 60 + "\n")
    f.write("End of transcript\n")
    f.write("=" * 60 + "\n")

print("wrote", OUT_PATH)
