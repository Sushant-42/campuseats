# Assignment 4 Notes

## A4. Resource Table

| Method | URL | What it does | Success code | Failure codes |
|---|---|---|---|---|
| POST | `/orders` | Creates a new order | 201 Created | 422 Invalid Request |
| GET | `/orders` | Lists orders, optionally filtered by student_id | 200 OK | 422 Invalid Request |
| GET | `/orders/{order_id}` | Returns one order by ID | 200 OK | 404 Not Found |
| PATCH | `/orders/{order_id}` | Updates the status of an order | 200 OK | 404 Not Found, 409 Conflict, 422 Invalid Request |
| POST | `/orders/{order_id}/cancellation` | Cancels an existing order through a state-changing sub-resource | 202 Accepted | 404 Not Found, 409 Conflict |

## A5. Hard Choice Justification

The operation that was least comfortable to model as a REST resource was order cancellation. In SOAP it could naturally be represented as a separate `cancelOrder()` operation, while REST encourages treating the order as a resource and representing cancellation as a state change. I chose `/orders/{order_id}/cancellation` as a state-changing sub-resource because it makes the cancellation action explicit while keeping it under the order resource. I rejected creating a completely separate top-level cancellation service because cancellation belongs to the lifecycle of a specific order.

## D3. Fallback Reasoning

If the Catalog service is unreachable, the Orders service uses a degraded fallback mode instead of failing the entire order creation request. The order can still be created using the item IDs and quantities supplied by the client, while Catalog information can be checked again when the dependency becomes available. This is preferable because a temporary Catalog outage should not completely prevent a student from placing an order, although the trade-off is that some Catalog information may temporarily be unavailable.

## 1. WSDL vs OpenAPI line count

Our Assignment 3 WSDL has 73 lines, while the OpenAPI YAML file has 245 lines.

The difference is 172 lines. The difference is mainly because the two contracts describe the service in different ways. The WSDL contains SOAP-specific structures such as XML Schema types, messages, port types, bindings, and service/port definitions. The OpenAPI file mainly describes HTTP endpoints, request/response formats, parameters, and status codes.

Two things declared in the WSDL that the OpenAPI file does not need are:

1. SOAP binding and SOAPAction information.
2. WSDL message/portType definitions for SOAP operations.

## 2. SOAP Fault vs REST error

In Assignment 3, one SOAP fault was:

```text
faultcode: soap:Client
errorCode: CARD_DECLINED

It was mapped by the CampusEats service to:

Status Code: 400 Bad Request

Problem body:

{
  "type": "about:blank",
  "title": "payment declined",
  "status": 400,
  "detail": "payment declined"
}

The Assignment 3 design mapped the CARD_DECLINED SOAP fault to a 400 domain error.

Returning this error inside a 200 OK response is a problem because systems in between the client and service, such as proxies, gateways, monitoring systems and caches, interpret 200 as a successful request. They may therefore treat a failed operation as successful. Using the correct HTTP status code allows the network and client software to correctly understand that the operation failed.

3. UDDI: publish, find, bind

In the new REST setup, the three UDDI moves do not exist in exactly the same form.

The main ideas that remain are:

Publish: the service publishes its API contract through OpenAPI.
Find: clients can discover the service through its API documentation or service registry.
Bind: the client uses the documented HTTP endpoint to call the service.

The old UDDI registry mechanism is not required. The OpenAPI contract and normal HTTP URLs take over much of the discovery and binding job.

4. XML Schema validation vs OpenAPI validation

The specific function in my code that carries the request-validation responsibility is:

create_order()

It checks the request body, required fields, item structure, and quantity before creating the order.

For example, it checks:

student_id
restaurant_id
items
item_id
quantity
positive quantity

Without this validation, a request such as:

{
  "student_id": "S001",
  "restaurant_id": "R001",
  "items": [
    {
      "item_id": "I001",
      "quantity": 0
    }
  ]
}

could get through even though the quantity should be at least 1.

5. Where I would still choose SOAP over REST

We would still choose SOAP for the external payment gateway used by CampusEats.

The reason is that payment processing can require a strict contract, message-level security and enterprise transaction reliability. In Assignment 3, SOAP was selected for the UniPay banking edge because of its rigid contract-first design, XML Schema validation, WS-Security and transactional reliability.

The guarantee we would be buying is stronger contract and message-level guarantees for a sensitive financial transaction, rather than relying only on HTTP-level REST semantics.