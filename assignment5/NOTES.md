# Assignment 5 Notes - HTTP Methods & Headers

Team ID: 5
Sushant Prashant Prabhavalakar - 20251651093
Harsh Yadav - 20251651042

This builds directly on the Assignment 4 CampusEats Orders service. The
resource model, endpoints and error format are unchanged; what's new is
correct method usage, and the header behavior described below.

---

## A1. CampusEats method map (updated from Assignment 4)

| # | Method | URL | Action | Success | Failure codes |
|---|---|---|---|---|---|
| 1 | POST | `/orders` | Create an order | 201 Created (+ `Location`) | 400, 401, 406, 422, 429 |
| 1b | POST | `/orders` (same `Idempotency-Key` replayed) | Return the original order, no duplicate | 200 OK | - |
| 2 | GET | `/orders` | List orders - filter by `student_id`, `sort`, `order`, `limit`, `offset` | 200 OK | 406, 422 |
| 3 | GET | `/orders/{order_id}` | Read one order | 200 OK (304 if `If-None-Match` matches) | 404 |
| 4 | PATCH | `/orders/{order_id}` | Update order status (state machine) | 200 OK | 400, 401, 404, 409, 412, 422, 429 |
| 5 | POST | `/orders/{order_id}/cancellation` | Cancel an order (non-CRUD action, modeled as a state-changing sub-resource, not a verb in the URL) | 202 Accepted | 401, 404, 409, 429 |
| 6 | OPTIONS | `/orders`, `/orders/{order_id}` | Discover allowed methods / CORS preflight | 200 OK + `Allow` | - |

No verb ever leaked into a URL - the one non-CRUD action (`cancel`) is a
noun sub-resource (`/cancellation`) under the order, not `POST
/orders/42/cancel` written as a verb call.

## A3. Safe / idempotent classification

| Endpoint | Safe? | Idempotent? | Notes |
|---|---|---|---|
| GET /orders | Yes | Yes | Read-only, no state change, repeatable |
| GET /orders/{id} | Yes | Yes | Same as above; also supports conditional GET |
| POST /orders | No | Yes (via `Idempotency-Key`) | Without the key it would create a new order every retry; the key makes retries return the original order instead |
| PATCH /orders/{id} | No | Depends on the transition | Setting a status to its current value is a no-op (idempotent by construction); moving it to a *new* status is not naturally idempotent, so we added `If-Match` so a client can safely retry a write without double-applying an unrelated change |
| POST /orders/{id}/cancellation | No | Yes in effect | Cancelling an already-cancelled order returns 409 rather than "succeeding again", so retrying a cancel call never does anything new |

No GET ever changes state - confirmed by inspection: `get_order_by_id` and
`list_orders` only read from the in-memory store.

## A6. One full request/response exchange

Request:
```
POST /orders/f46a417f-cc00-42ba-bb7c-b74b9956990d/cancellation HTTP/1.1
Host: localhost:8000
Authorization: Bearer tok-ratelimit-demo
```

Response:
```
HTTP/1.1 202 ACCEPTED
Server: Werkzeug/3.1.7 Python/3.12.3
Content-Type: application/json
X-Content-Type-Options: nosniff
Strict-Transport-Security: max-age=63072000; includeSubDomains
Access-Control-Allow-Origin: *
X-RateLimit-Limit: 5
X-RateLimit-Remaining: 4
Connection: close
```
(Captured live in `curl-transcript.txt`, section 16b, call 1.)

---

## D2. Headers table

| Endpoint | Request headers it needs/honours | Response headers it sets |
|---|---|---|
| POST /orders | `Authorization: Bearer <token>` (required), `Idempotency-Key` (required), `Content-Type: application/json`, `Accept` | `Location`, `Content-Type`, `Cache-Control: no-store`, `X-RateLimit-Limit`, `X-RateLimit-Remaining`, security + CORS headers (all endpoints, see below) |
| GET /orders | `Accept`, `Accept-Encoding` | `Content-Type`, `Content-Encoding: gzip` (when applicable), `Vary: Accept-Encoding` |
| GET /orders/{id} | `Accept`, `If-None-Match` | `ETag`, `Cache-Control: private, max-age=30` |
| PATCH /orders/{id} | `Authorization: Bearer <token>` (required), `If-Match` (optional), `Content-Type` | `ETag`, `Cache-Control: no-store`, `X-RateLimit-Limit`, `X-RateLimit-Remaining` |
| POST /orders/{id}/cancellation | `Authorization: Bearer <token>` (required) | `X-RateLimit-Limit`, `X-RateLimit-Remaining` |
| OPTIONS /orders, /orders/{id} | `Origin`, `Access-Control-Request-Method` | `Allow`, `Access-Control-Allow-Methods`, `Access-Control-Allow-Headers` |
| *every* response | - | `X-Content-Type-Options: nosniff`, `Strict-Transport-Security`, `Access-Control-Allow-Origin: *` |

## C4. The safe-retry plan

| Risky endpoint | Mechanism | Why |
|---|---|---|
| POST /orders | `Idempotency-Key` | Create is unsafe and (without help) not idempotent - a network retry would otherwise create a second order for the same request. The key lets a retry return the original 201 body as a 200 instead. |
| PATCH /orders/{id} | `If-Match` | Update is unsafe and only accidentally idempotent. If two editors read the order, then both submit a change, the second write would silently clobber the first without `If-Match`. Requiring the client's ETag to still match guarantees the write is against the version it thinks it's against. |
| POST /orders/{id}/cancellation | Domain state check (`if order.status in [delivered, cancelled]: 409`) rather than a client-supplied key | Cancellation only has one meaningful "unsafe" outcome (moving to `cancelled`), and that state is naturally terminal. Checking current status before applying the change makes a retried cancel call either a no-op-with-409 or simply never double-applies, without needing a separate idempotency key. |

---

## D3 / NOTES.md required answers

### 1. Three endpoints - method, success status, the one response header that matters most

- **POST /orders** - method: POST, success: 201 Created. The header that
  matters most is **`Location`**, because it's the only place the client
  learns the new order's URL; without it the client would have to guess it
  from the response body.
- **GET /orders/{order_id}** - method: GET, success: 200 OK. The header
  that matters most is **`ETag`**, because it's what makes conditional GET
  (304) and conditional PATCH (`If-Match`) possible - everything in Part C
  depends on it.
- **POST /orders/{order_id}/cancellation** - method: POST, success: 202
  Accepted. The header that matters most is **`X-RateLimit-Remaining`**,
  because it's a state-changing action a client might be tempted to retry
  aggressively, and this header is the client's only warning that it's
  about to be throttled.

### 2. Which endpoints are safe/idempotent; which is neither, and how it was made retry-safe

Covered in the **A3 table** above. The one endpoint that is neither safe
nor naturally idempotent is **PATCH /orders/{id}** when it's making a real
transition (e.g. `pending -> confirmed`): it changes state, and applying
the same PATCH twice in a row could mean "confirm, then try to confirm an
already-confirmed order again" if the client's view of state is stale.
We made it retry-safe with the `If-Match` conditional write from Part C: a
retried PATCH either matches the ETag the client expects (safe to apply)
or gets rejected with 412 (safe to *not* apply blindly).

### 3. One ETag, the 304 request, the 412 write - what each prevents

From a real run (see `curl-transcript.txt`, sections 7-10):

- ETag from `GET /orders/{id}`: `"d632e44fed1fac7410db278cba357683"`
- Conditional GET that returns 304:
  `curl -v -sS $BASE/orders/{id} -H 'If-None-Match: "d632e44fed1fac7410db278cba357683"'`
  → **saves bandwidth** - the client already has the current representation,
  so the server sends an empty body instead of repeating the same JSON.
- Conditional write that returns 412:
  `curl -v -sS -X PATCH $BASE/orders/{id} -H 'If-Match: "stale-etag-value"' --data-raw '{"status":"confirmed"}'`
  → **prevents a lost update** - it stops the client from overwriting a
  version of the order it never actually saw (a stale read followed by a
  blind write).

### 4. One request that returns 422, one that returns 400 - what's the difference

- **400** (malformed - the server can't even parse the request):
  `curl -X POST $BASE/orders -H "Authorization: Bearer t" -H "Idempotency-Key: k" -d "{bad json"`
  → body isn't valid JSON at all.
- **422** (well-formed JSON, but fails domain rules):
  `curl -X POST $BASE/orders -H "Authorization: Bearer t" -H "Idempotency-Key: k" --data-raw '{"student_id":"S100"}'`
  → valid JSON object, but missing the required `restaurant_id` and
  `items` fields.

The difference: 400 means "I don't understand what you sent me as HTTP/JSON
at all"; 422 means "I understood it perfectly, but it doesn't satisfy the
rules of this resource."

### 5. Browser on another origin blocked, server logs show 200 - who blocked it, and the fix

The **browser itself** blocked it, enforcing the Same-Origin Policy /
CORS: the request did reach the server and the server did respond with
200, but the browser refused to hand that response to the page's
JavaScript because the response didn't carry permission for that origin.
The fix is the **`Access-Control-Allow-Origin`** response header (this
service sets it to `*` on every response, and additionally answers the
`OPTIONS` preflight with `Access-Control-Allow-Methods` /
`Access-Control-Allow-Headers`).

### 6. One response with cacheable Cache-Control, one with no-store - why each

- **Cacheable**: `GET /orders/{id}` → `Cache-Control: private, max-age=30`.
  It's a plain read of something that doesn't change often; letting the
  client (not a shared proxy, hence `private`) reuse it for 30 seconds
  avoids needless repeat requests, and the `ETag` still lets it revalidate
  cheaply after that.
- **no-store**: `POST /orders` (201) and `PATCH /orders/{id}` (200) →
  `Cache-Control: no-store`. These respond to state-changing requests; a
  cached copy of "the order was just created/updated" is meaningless (and
  potentially misleading) for a future unrelated request to the same URL,
  so caches must not store it at all.

### 7. Search endpoint is a GET - when POST would be right instead, and the trade-off

`GET /orders` is right as long as the filter/sort/pagination fits in a
query string and the search itself doesn't need to be logged or paged
through a very large, sensitive filter body. POST would be the better
choice if the search criteria became **large or sensitive** (e.g. a
complex filter object that doesn't fit cleanly in a URL, or one containing
data that shouldn't sit in server/proxy access logs and browser history).
What you give up by switching to POST: **safety and idempotence
guarantees** - the request is no longer automatically cacheable, no longer
safely re-orderable by intermediaries, and no longer bookmarkable/shareable
as a URL.

### 8. Location on 201 vs 3xx - what it points to in each case

- On **201 Created**, `Location` points to the **new resource that was
  just created** - e.g. `/orders/{order_id}` for the order this request
  made.
- On a **3xx redirect**, `Location` points to **where the client should go
  instead** to get the resource it actually asked for (a different URL for
  the *same* logical thing it originally requested, not something newly
  created). This service doesn't currently issue a 3xx anywhere, but the
  semantics are what we'd apply if, for example, `/orders/{id}` were ever
  aliased to a canonical URL.

---

## What's carried over unchanged from Assignment 4

- Resource model, in-memory store, `Order`/`OrderItem` dataclasses.
- Problem/`about:blank` JSON error shape for every 4xx/5xx.
- Catalog service call with timeout, retry + backoff/jitter, and fallback
  mode when the Catalog is unreachable (`service/gateway.py`).
- The PATCH status state machine (`pending -> confirmed -> preparing ->
  ready -> delivered`, with `cancelled` reachable from `pending`/`confirmed`).
- Assignment 3/4 SOAP-vs-REST discussion questions (kept in this file's
  git history / prior submission - not repeated here since Assignment 5
  only asks for the eight questions above).
