
CREATE DATABASE IF NOT EXISTS campuseats_graphql;
USE campuseats_graphql;

CREATE TABLE IF NOT EXISTS dishes (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    price DECIMAL(10,2) NOT NULL,
    available BOOLEAN NOT NULL DEFAULT TRUE
);

INSERT INTO dishes (name, price, available)
VALUES
    ('Paneer Roll', 90.00, TRUE),
    ('Veg Burger', 70.00, TRUE),
    ('Margherita Pizza', 150.00, TRUE);
