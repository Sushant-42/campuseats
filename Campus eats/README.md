# CampusEats — GraphQL Menu Service

## Selected Service
**Menu/Dishes Service**

This service allows clients to retrieve the menu and add new dishes using GraphQL.

## Technologies Used
- Node.js
- Apollo Server
- GraphQL
- MySQL
- mysql2
- Express
- HTML, CSS, and JavaScript

## Project Files
- `schema.graphql` — GraphQL types, queries, and mutations
- `server.js` — Apollo Server and SQL-backed resolvers
- `db.js` — MySQL connection pool
- `schema.sql` — database and table setup with sample data
- `public/index.html` — frontend interface

## How to Run

1. Install Node.js and MySQL.
2. Create the database and table using `schema.sql`.
3. Update the MySQL password in `db.js`.
4. Open a terminal in the project folder.
5. Install dependencies:

   ```bash
   npm install
   ```

6. Start the server:

   ```bash
   node server.js
   ```

7. Open `http://localhost:4000/` in your browser.

The GraphQL endpoint is `http://localhost:4000/graphql`.

## Assignment Questions

### 1. Which CampusEats service did you choose?
I chose the Menu/Dishes Service, which retrieves dishes and adds new dishes using GraphQL.

### 2. Name one field the client can skip and one it cannot. Why?
The client can skip `available` when it does not need availability information, because GraphQL lets clients select only the fields they want. However, `name` is non-null in the schema (`String!`), so it cannot be returned as `null`.

### 3. How does a GraphQL query map to SQL?
The `dishes` query calls the `Query.dishes` resolver, which executes `SELECT id, name, price, available FROM dishes`. The `dish(id: ID!)` query uses a SQL `WHERE id = ?` condition to retrieve a particular dish. The `addDish` mutation calls the `Mutation.addDish` resolver, which executes an SQL `INSERT` statement.

## Team Members
- Roll Number: 20251651093
- Name: Sushant prashant Prabhavalkar
- Roll Number: 20251651042
- Name: Harsh Yadav
