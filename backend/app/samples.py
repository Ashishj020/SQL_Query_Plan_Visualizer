from .models import SampleQuery

SAMPLES: list[SampleQuery] = [
    SampleQuery(
        id="missing-index",
        title="Missing index",
        blurb="Month of shipped orders — status + date have no index.",
        sql=(
            "SELECT id, customer_id, total, created_at\n"
            "FROM orders\n"
            "WHERE status = 'shipped'\n"
            "  AND created_at >= TIMESTAMP '2024-06-01'\n"
            "  AND created_at <  TIMESTAMP '2024-07-01';"
        ),
    ),
    SampleQuery(
        id="unindexed-join",
        title="Unindexed join",
        blurb="Lookup one customer, then scan every order to find theirs.",
        sql=(
            "SELECT c.email, o.id, o.total, o.status\n"
            "FROM customers c\n"
            "JOIN orders o ON o.customer_id = c.id\n"
            "WHERE c.email = 'user42@example.com';"
        ),
    ),
    SampleQuery(
        id="top-revenue",
        title="Top revenue",
        blurb="Quarterly product revenue — aggregates 540k items without a date index.",
        sql=(
            "SELECT p.id, p.name,\n"
            "       SUM(oi.quantity * oi.unit_price) AS revenue\n"
            "FROM order_items oi\n"
            "JOIN products p ON p.id = oi.product_id\n"
            "WHERE oi.created_at >= TIMESTAMP '2024-06-01'\n"
            "  AND oi.created_at <  TIMESTAMP '2024-06-10'\n"
            "GROUP BY p.id, p.name\n"
            "ORDER BY revenue DESC\n"
            "LIMIT 20;"
        ),
    ),
    SampleQuery(
        id="fuzzy-search",
        title="Fuzzy search",
        blurb="Leading-wildcard ILIKE on 250k review bodies.",
        sql=(
            "SELECT id, product_id, rating, left(body, 72) AS excerpt\n"
            "FROM reviews\n"
            "WHERE body ILIKE '%disappointed%'\n"
            "   OR body ILIKE '%broken%';"
        ),
    ),
    SampleQuery(
        id="correlated-subquery",
        title="Correlated subquery",
        blurb="Per-customer last order via a subquery — repeats a seq scan.",
        sql=(
            "SELECT c.id, c.name, c.city,\n"
            "       (SELECT MAX(o.created_at)\n"
            "          FROM orders o\n"
            "         WHERE o.customer_id = c.id) AS last_order_at\n"
            "FROM customers c\n"
            "WHERE c.city = 'Austin'\n"
            "  AND c.id <= 2500;"
        ),
    ),
]
