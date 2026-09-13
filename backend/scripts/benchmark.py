"""Run the five demo queries before and after the advisor's recommended fixes.

Indexes are created for the "after" timings, then dropped again so the live
app still shows the interesting sequential-scan plans.
"""

from __future__ import annotations

import statistics
import sys
import time
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / "backend") not in sys.path:
    sys.path.insert(0, str(ROOT / "backend"))

from app.config import settings  # noqa: E402
from app.samples import SAMPLES  # noqa: E402

RUNS = 3

INDEX_FIXES = [
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE INDEX IF NOT EXISTS idx_orders_status_created ON orders (status, created_at)",
    "CREATE INDEX IF NOT EXISTS idx_customers_email ON customers (email)",
    "CREATE INDEX IF NOT EXISTS idx_orders_customer_id ON orders (customer_id)",
    "CREATE INDEX IF NOT EXISTS idx_order_items_created_product ON order_items (created_at, product_id) INCLUDE (quantity, unit_price)",
    "CREATE INDEX IF NOT EXISTS idx_reviews_body_trgm ON reviews USING gin (body gin_trgm_ops)",
    "CREATE INDEX IF NOT EXISTS idx_customers_city ON customers (city)",
    "CREATE INDEX IF NOT EXISTS idx_orders_customer_created ON orders (customer_id, created_at)",
]

DROP_FIXES = [
    "DROP INDEX IF EXISTS idx_orders_status_created",
    "DROP INDEX IF EXISTS idx_customers_email",
    "DROP INDEX IF EXISTS idx_orders_customer_id",
    "DROP INDEX IF EXISTS idx_order_items_created_product",
    "DROP INDEX IF EXISTS idx_reviews_body_trgm",
    "DROP INDEX IF EXISTS idx_customers_city",
    "DROP INDEX IF EXISTS idx_orders_customer_created",
]

# Same intent as Q5, rewritten so the planner can hash-join / group once.
Q5_REWRITE = """SELECT c.id, c.name, c.city, MAX(o.created_at) AS last_order_at
FROM customers c
LEFT JOIN orders o ON o.customer_id = c.id
WHERE c.city = 'Austin'
  AND c.id <= 2500
GROUP BY c.id, c.name, c.city;"""


def median_ms(conn: psycopg.Connection, sql: str) -> float:
    samples: list[float] = []
    for _ in range(RUNS):
        t0 = time.perf_counter()
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = '120000'")
            cur.execute(f"EXPLAIN (ANALYZE, FORMAT JSON)\n{sql}")
            payload = cur.fetchone()[0]
        elapsed = (time.perf_counter() - t0) * 1000
        exec_ms = float(payload[0].get("Execution Time") or elapsed)
        samples.append(exec_ms)
    return statistics.median(samples)


def apply(conn: psycopg.Connection, statements: list[str]) -> None:
    with conn.cursor() as cur:
        for stmt in statements:
            cur.execute(stmt)
        cur.execute("ANALYZE")
    conn.commit()


def write_report(rows: list[dict]) -> None:
    lines = [
        "# Before / after execution times",
        "",
        "Measured with `EXPLAIN (ANALYZE)` against the seeded `shop` database",
        f"(median of {RUNS} runs). Indexes are applied only for the after pass,",
        "then dropped so the UI still demonstrates the slow plans.",
        "",
        "| # | Query | Bottleneck | Before | After | Speedup |",
        "|---|-------|------------|--------|-------|---------|",
    ]
    details = []
    for row in rows:
        speedup = row["before"] / row["after"] if row["after"] else float("inf")
        lines.append(
            f"| {row['n']} | {row['title']} | {row['bottleneck']} | "
                f"{row['before']:.1f} ms | {row['after']:.1f} ms | {speedup:.1f}x |"
        )
        details.extend(
            [
                "",
                f"## {row['n']}. {row['title']}",
                "",
                f"**Bottleneck:** {row['bottleneck']}",
                "",
                "Before:",
                "",
                "```sql",
                row["before_sql"],
                "```",
                "",
                "Fix applied:",
                "",
                "```sql",
                row["fix"],
                "```",
                "",
                f"After query (same unless noted):",
                "",
                "```sql",
                row["after_sql"],
                "```",
                "",
                f"Result: **{row['before']:.1f} ms -> {row['after']:.1f} ms** "
                f"({speedup:.1f}x).",
            ]
        )
    (ROOT / "BENCHMARKS.md").write_text("\n".join(lines + details) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    stories = [
        {
            "sample": "missing-index",
            "bottleneck": "Seq Scan on orders (status + month filter)",
            "fix": "CREATE INDEX idx_orders_status_created ON orders (status, created_at);",
            "after_sql": None,
        },
        {
            "sample": "unindexed-join",
            "bottleneck": "Seq Scan customers + Seq Scan orders",
            "fix": "CREATE INDEX idx_customers_email ON customers (email);\nCREATE INDEX idx_orders_customer_id ON orders (customer_id);",
            "after_sql": None,
        },
        {
            "sample": "top-revenue",
            "bottleneck": "Seq Scan of 540k order_items + HashAggregate",
            "fix": "CREATE INDEX idx_order_items_created_product ON order_items (created_at, product_id) INCLUDE (quantity, unit_price);",
            "after_sql": None,
        },
        {
            "sample": "fuzzy-search",
            "bottleneck": "ILIKE leading-wildcard Seq Scan on reviews",
            "fix": "CREATE EXTENSION pg_trgm;\nCREATE INDEX idx_reviews_body_trgm ON reviews USING gin (body gin_trgm_ops);",
            "after_sql": None,
        },
        {
            "sample": "correlated-subquery",
            "bottleneck": "Correlated MAX() subquery + missing join index",
            "fix": "CREATE INDEX idx_customers_city ON customers (city);\nCREATE INDEX idx_orders_customer_created ON orders (customer_id, created_at);\n-- plus rewrite to JOIN + GROUP BY",
            "after_sql": Q5_REWRITE,
        },
    ]
    by_id = {s.id: s for s in SAMPLES}

    with psycopg.connect(settings.database_url) as conn:
        apply(conn, DROP_FIXES)
        before: dict[str, float] = {}
        for story in stories:
            sample = by_id[story["sample"]]
            print(f"timing before: {sample.title}")
            before[sample.id] = median_ms(conn, sample.sql)
            print(f"  {before[sample.id]:.1f} ms")

        apply(conn, INDEX_FIXES)
        after: dict[str, float] = {}
        for story in stories:
            sample = by_id[story["sample"]]
            sql = story["after_sql"] or sample.sql
            print(f"timing after:  {sample.title}")
            after[sample.id] = median_ms(conn, sql)
            print(f"  {after[sample.id]:.1f} ms")

        apply(conn, DROP_FIXES)

    rows = []
    for i, story in enumerate(stories, start=1):
        sample = by_id[story["sample"]]
        rows.append(
            {
                "n": i,
                "title": sample.title,
                "bottleneck": story["bottleneck"],
                "before": before[sample.id],
                "after": after[sample.id],
                "before_sql": sample.sql,
                "after_sql": story["after_sql"] or sample.sql,
                "fix": story["fix"],
            }
        )
    write_report(rows)


if __name__ == "__main__":
    main()
