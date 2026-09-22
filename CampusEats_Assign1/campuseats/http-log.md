# HTTP Request/Response Log

## Request 1 — Get User 1

### Request

GET https://jsonplaceholder.typicode.com/users/1

Command used:

curl.exe -i https://jsonplaceholder.typicode.com/users/1

### Response

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

Response body:

{
  "id": 1,
  "name": "Leanne Graham",
  "username": "Bret",
  "email": "Sincere@april.biz"
}

### Annotation

- Status code: 200 OK — the request was successful.
- Content-Type: application/json — the response body is JSON data.

## Request 2 — Get User 2

### Request

GET https://jsonplaceholder.typicode.com/users/2

Command used:

curl.exe -i https://jsonplaceholder.typicode.com/users/2

### Response

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

Response body:

{
  "id": 2,
  "name": "Ervin Howell",
  "username": "Antonette",
  "email": "Shanna@melissa.tv"
}

### Annotation

- Status code: 200 OK — the request was successful.
- Content-Type: application/json — the response body is JSON data.

## Request 3 — Get Post 1

### Request

GET https://jsonplaceholder.typicode.com/posts/1

Command used:

curl.exe -i https://jsonplaceholder.typicode.com/posts/1

### Response

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

Response body:

{
  "userId": 1,
  "id": 1,
  "title": "sunt aut facere repellat provident occaecati excepturi optio reprehenderit",
  "body": "quia et suscipit\nsuscipit recusandae consequuntur expedita et cum\nreprehenderit molestiae ut ut quas totam\nnostrum rerum est autem sunt rem eveniet architecto"
}

### Annotation

- Status code: 200 OK — the request was successful.
- Content-Type: application/json — the response body is JSON data.

## Request 4 — Get Comment 1

### Request

GET https://jsonplaceholder.typicode.com/comments/1

Command used:

curl.exe -i https://jsonplaceholder.typicode.com/comments/1

### Response

HTTP/1.1 200 OK
Content-Type: application/json; charset=utf-8

Response body:

{
  "postId": 1,
  "id": 1,
  "name": "id labore ex et quam laborum",
  "email": "Eliseo@gardner.biz",
  "body": "laudantium enim quasi est quidem magnam voluptate ipsam eos\ntempora quo necessitatibus\ndolor quam autem quasi\nreiciendis et nam sapiente accusantium"
}

### Annotation

- Status code: 200 OK — the request was successful.
- Content-Type: application/json — the response body is JSON data.

## Request 5 — Non-existent User

### Request

GET https://jsonplaceholder.typicode.com/users/9999

Command used:

curl.exe -i https://jsonplaceholder.typicode.com/users/9999

### Response

HTTP/1.1 404 Not Found
Content-Type: application/json; charset=utf-8

Response body:

{}

### Annotation

- Status code: 404 Not Found — the requested resource could not be found.
- Content-Type: application/json — the response body is JSON data.



