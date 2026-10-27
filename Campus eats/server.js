
const { ApolloServer } = require('@apollo/server');
const { expressMiddleware } = require('@as-integrations/express5');
const { ApolloServerPluginDrainHttpServer } = require('@apollo/server/plugin/drainHttpServer');

const express = require('express');
const cors = require('cors');
const http = require('http');
const fs = require('fs');
const path = require('path');

const pool = require('./db');

// Load the GraphQL schema
const typeDefs = fs.readFileSync(
    path.join(__dirname, 'schema.graphql'),
    'utf8'
);

// GraphQL resolvers
const resolvers = {
    Query: {
        // Fetch all dishes
        dishes: async () => {
            const [rows] = await pool.query(
                'SELECT id, name, price, available FROM dishes'
            );

            return rows;
        },

        // Fetch one dish by ID
        dish: async (_, { id }) => {
            const [rows] = await pool.query(
                'SELECT id, name, price, available FROM dishes WHERE id = ?',
                [id]
            );

            return rows[0] || null;
        }
    },

    Mutation: {
        // Add a new dish
        addDish: async (_, { input }) => {
            const { name, price, available = true } = input;

            const [result] = await pool.query(
                'INSERT INTO dishes (name, price, available) VALUES (?, ?, ?)',
                [name, price, available]
            );

            // Retrieve the newly inserted dish
            const [rows] = await pool.query(
                'SELECT id, name, price, available FROM dishes WHERE id = ?',
                [result.insertId]
            );

            return rows[0];
        }
    }
};

async function startServer() {
    const app = express();
    const httpServer = http.createServer(app);

    const server = new ApolloServer({
        typeDefs,
        resolvers,
        plugins: [
            ApolloServerPluginDrainHttpServer({ httpServer })
        ]
    });

    await server.start();

    // Serve the frontend from the public folder
    app.use(express.static(path.join(__dirname, 'public')));

    // Configure the GraphQL endpoint
    app.use(
        '/graphql',
        cors(),
        express.json(),
        expressMiddleware(server)
    );

    await new Promise((resolve) => {
        httpServer.listen(4000, resolve);
    });

    console.log('CampusEats website: http://localhost:4000/');
    console.log('GraphQL endpoint: http://localhost:4000/graphql');
}

startServer().catch((error) => {
    console.error('Failed to start CampusEats server:', error);
});
