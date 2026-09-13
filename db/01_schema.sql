-- Intentionally no secondary indexes. Only primary keys exist so the
-- sample queries exercise sequential scans, nested loops, and sorts.

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    email       TEXT        NOT NULL,
    city        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        TEXT        NOT NULL,
    description TEXT        NOT NULL,
    category    TEXT        NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE orders (
    id          SERIAL PRIMARY KEY,
    customer_id INTEGER     NOT NULL,
    status      TEXT        NOT NULL,
    total       NUMERIC(12, 2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER     NOT NULL,
    product_id  INTEGER     NOT NULL,
    quantity    INTEGER     NOT NULL,
    unit_price  NUMERIC(10, 2) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);

CREATE TABLE reviews (
    id          SERIAL PRIMARY KEY,
    product_id  INTEGER     NOT NULL,
    customer_id INTEGER     NOT NULL,
    rating      INTEGER     NOT NULL,
    body        TEXT        NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL
);
