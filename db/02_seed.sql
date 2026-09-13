-- ~40k customers, 10k products, 180k orders, 540k items, 250k reviews.
-- generate_series keeps first-boot time reasonable while still producing
-- plans that are visibly expensive without supporting indexes.

INSERT INTO customers (name, email, city, created_at)
SELECT
    'Customer ' || i,
    'user' || i || '@example.com',
    (ARRAY[
        'Austin', 'Denver', 'Seattle', 'Boston', 'Miami',
        'Chicago', 'Portland', 'Atlanta', 'Dallas', 'Phoenix'
    ])[1 + (i % 10)],
    TIMESTAMP '2023-01-01'
        + ((i % 700) * INTERVAL '1 day')
        + ((i % 24) * INTERVAL '1 hour')
FROM generate_series(1, 40000) AS i;

INSERT INTO products (name, description, category, price, created_at)
SELECT
    (ARRAY['Wireless', 'Classic', 'Pro', 'Lite', 'Ultra'])[1 + (i % 5)]
        || ' '
        || (ARRAY['Headphones', 'Keyboard', 'Mouse', 'Speaker', 'Charger', 'Cable', 'Stand', 'Case'])[1 + (i % 8)]
        || ' '
        || i,
    'High quality '
        || (ARRAY['wireless audio gear', 'ergonomic accessory', 'durable electronics'])[1 + (i % 3)]
        || ' model '
        || i
        || ' with extended warranty and premium finish.',
    (ARRAY['audio', 'accessories', 'power', 'cables'])[1 + (i % 4)],
    ROUND((9.99 + (i % 220))::NUMERIC, 2),
    TIMESTAMP '2023-01-01' + ((i % 400) * INTERVAL '1 day')
FROM generate_series(1, 10000) AS i;

INSERT INTO orders (customer_id, status, total, created_at)
SELECT
    1 + (i % 40000),
    (ARRAY['pending', 'paid', 'shipped', 'delivered', 'cancelled'])[1 + (i % 5)],
    ROUND((18 + (i % 480))::NUMERIC, 2),
    TIMESTAMP '2023-01-01'
        + ((i % 730) * INTERVAL '1 day')
        + ((i % 86400) * INTERVAL '1 second')
FROM generate_series(1, 180000) AS i;

INSERT INTO order_items (order_id, product_id, quantity, unit_price, created_at)
SELECT
    1 + (i % 180000),
    1 + (i % 10000),
    1 + (i % 5),
    ROUND((9.99 + (i % 220))::NUMERIC, 2),
    TIMESTAMP '2023-01-01' + ((i % 730) * INTERVAL '1 day')
FROM generate_series(1, 540000) AS i;

INSERT INTO reviews (product_id, customer_id, rating, body, created_at)
SELECT
    1 + (i % 10000),
    1 + (i % 40000),
    1 + (i % 5),
    repeat('Quality notes for this purchase. ', 6)
        || CASE
            WHEN i % 37 = 0 THEN 'Customer was disappointed with shipping and the item arrived broken.'
            WHEN i % 41 = 0 THEN 'Wireless pairing dropped and the unit felt cheap.'
            ELSE 'Satisfied overall with packaging and delivery speed.'
           END,
    TIMESTAMP '2023-06-01' + ((i % 450) * INTERVAL '1 day')
FROM generate_series(1, 250000) AS i;

ANALYZE customers;
ANALYZE products;
ANALYZE orders;
ANALYZE order_items;
ANALYZE reviews;
