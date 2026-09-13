# Before / after execution times

Measured with `EXPLAIN (ANALYZE)` against the seeded `shop` database
(median of 3 runs). Indexes are applied only for the after pass,
then dropped so the UI still demonstrates the slow plans.

| # | Query | Bottleneck | Before | After | Speedup |
|---|-------|------------|--------|-------|---------|
| 1 | Missing index | Seq Scan on orders (status + month filter) | 11.8 ms | 0.5 ms | 22.2x |
| 2 | Unindexed join | Seq Scan customers + Seq Scan orders | 20.2 ms | 0.1 ms | 361.3x |
| 3 | Top revenue | Seq Scan of 540k order_items + HashAggregate | 41.7 ms | 9.5 ms | 4.4x |
| 4 | Fuzzy search | ILIKE leading-wildcard Seq Scan on reviews | 883.8 ms | 24.0 ms | 36.8x |
| 5 | Correlated subquery | Correlated MAX() subquery + missing join index | 1431.7 ms | 1.1 ms | 1291.0x |

## 1. Missing index

**Bottleneck:** Seq Scan on orders (status + month filter)

Before:

```sql
SELECT id, customer_id, total, created_at
FROM orders
WHERE status = 'shipped'
  AND created_at >= TIMESTAMP '2024-06-01'
  AND created_at <  TIMESTAMP '2024-07-01';
```

Fix applied:

```sql
CREATE INDEX idx_orders_status_created ON orders (status, created_at);
```

After query (same unless noted):

```sql
SELECT id, customer_id, total, created_at
FROM orders
WHERE status = 'shipped'
  AND created_at >= TIMESTAMP '2024-06-01'
  AND created_at <  TIMESTAMP '2024-07-01';
```

Result: **11.8 ms -> 0.5 ms** (22.2x).

## 2. Unindexed join

**Bottleneck:** Seq Scan customers + Seq Scan orders

Before:

```sql
SELECT c.email, o.id, o.total, o.status
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE c.email = 'user42@example.com';
```

Fix applied:

```sql
CREATE INDEX idx_customers_email ON customers (email);
CREATE INDEX idx_orders_customer_id ON orders (customer_id);
```

After query (same unless noted):

```sql
SELECT c.email, o.id, o.total, o.status
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE c.email = 'user42@example.com';
```

Result: **20.2 ms -> 0.1 ms** (361.3x).

## 3. Top revenue

**Bottleneck:** Seq Scan of 540k order_items + HashAggregate

Before:

```sql
SELECT p.id, p.name,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p ON p.id = oi.product_id
WHERE oi.created_at >= TIMESTAMP '2024-06-01'
  AND oi.created_at <  TIMESTAMP '2024-06-10'
GROUP BY p.id, p.name
ORDER BY revenue DESC
LIMIT 20;
```

Fix applied:

```sql
CREATE INDEX idx_order_items_created_product ON order_items (created_at, product_id) INCLUDE (quantity, unit_price);
```

After query (same unless noted):

```sql
SELECT p.id, p.name,
       SUM(oi.quantity * oi.unit_price) AS revenue
FROM order_items oi
JOIN products p ON p.id = oi.product_id
WHERE oi.created_at >= TIMESTAMP '2024-06-01'
  AND oi.created_at <  TIMESTAMP '2024-06-10'
GROUP BY p.id, p.name
ORDER BY revenue DESC
LIMIT 20;
```

Result: **41.7 ms -> 9.5 ms** (4.4x).

## 4. Fuzzy search

**Bottleneck:** ILIKE leading-wildcard Seq Scan on reviews

Before:

```sql
SELECT id, product_id, rating, left(body, 72) AS excerpt
FROM reviews
WHERE body ILIKE '%disappointed%'
   OR body ILIKE '%broken%';
```

Fix applied:

```sql
CREATE EXTENSION pg_trgm;
CREATE INDEX idx_reviews_body_trgm ON reviews USING gin (body gin_trgm_ops);
```

After query (same unless noted):

```sql
SELECT id, product_id, rating, left(body, 72) AS excerpt
FROM reviews
WHERE body ILIKE '%disappointed%'
   OR body ILIKE '%broken%';
```

Result: **883.8 ms -> 24.0 ms** (36.8x).

## 5. Correlated subquery

**Bottleneck:** Correlated MAX() subquery + missing join index

Before:

```sql
SELECT c.id, c.name, c.city,
       (SELECT MAX(o.created_at)
          FROM orders o
         WHERE o.customer_id = c.id) AS last_order_at
FROM customers c
WHERE c.city = 'Austin'
  AND c.id <= 2500;
```

Fix applied:

```sql
CREATE INDEX idx_customers_city ON customers (city);
CREATE INDEX idx_orders_customer_created ON orders (customer_id, created_at);
-- plus rewrite to JOIN + GROUP BY
```

After query (same unless noted):

```sql
SELECT c.id, c.name, c.city, MAX(o.created_at) AS last_order_at
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE c.city = 'Austin'
  AND c.id <= 2500
GROUP BY c.id, c.name, c.city;
```

Result: **1431.7 ms -> 1.1 ms** (1291.0x).
