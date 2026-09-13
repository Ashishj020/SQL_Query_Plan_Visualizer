from __future__ import annotations

import re
from typing import Iterable

from .models import PlanNode, Suggestion

_IDENT = re.compile(r"\b([a-zA-Z_][a-zA-Z0-9_]*)\b")
_SKIP_TOKENS = {
    "and",
    "or",
    "not",
    "is",
    "null",
    "true",
    "false",
    "numeric",
    "integer",
    "text",
    "date",
    "timestamp",
    "timestamptz",
    "boolean",
    "bpchar",
    "varchar",
    "any",
    "unknown",
    "like",
    "ilike",
    "between",
    "in",
    "case",
    "when",
    "then",
    "else",
    "end",
    "coalesce",
    "cast",
    "numeric",
}


_STRINGS = re.compile(r"'([^']|'')*'")


def advise(root: PlanNode) -> list[Suggestion]:
    found: list[Suggestion] = []
    _walk(root, None, found)
    found.sort(key=lambda s: {"high": 0, "medium": 1, "low": 2}[s.severity])
    # Stable de-dupe on title + relation + fix.
    seen: set[tuple[str, str, str]] = set()
    unique: list[Suggestion] = []
    for item in found:
        key = (item.title, item.relation or "", item.fix_sql)
        if key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique[:12]


def _walk(node: PlanNode, parent: PlanNode | None, out: list[Suggestion]) -> None:
    _seq_scan(node, parent, out)
    _like_pattern(node, out)
    _nested_loop(node, out)
    _sort(node, out)
    _row_estimate(node, out)
    _filter_waste(node, out)
    _hash_spill(node, out)
    _cte(node, out)
    _heap_fetches(node, out)
    _high_cost(node, out)
    for child in node.children:
        _walk(child, node, out)


def _seq_scan(node: PlanNode, parent: PlanNode | None, out: list[Suggestion]) -> None:
    if node.node_type != "Seq Scan" or not node.relation:
        return
    rows = node.actual_rows if node.actual_rows is not None else node.plan_rows
    removed = node.rows_removed_by_filter or 0
    costly = node.exclusive_cost_pct >= 8 or (rows or 0) >= 800 or removed >= 10_000
    if not costly:
        return
    cols = _columns_from(node.filter, node.index_cond)
    if not cols and parent:
        cols = _prefer_join_cols(
            _columns_from(parent.hash_cond, parent.join_filter, parent.index_cond)
        )
    index_sql = _index_sql(node.relation, cols, fallback="/* join or filter column */")
    predicate = node.filter or "no residual filter — the whole table is being read"
    out.append(
        Suggestion(
            id=f"seq-{node.id}",
            severity="high" if node.exclusive_cost_pct >= 15 or (rows or 0) >= 5000 else "medium",
            title=f"Sequential scan on {node.relation}",
            detail=(
                f"{node.relation} is being read end-to-end"
                f"{_cost_clause(node)}. Filter: {predicate}. "
                "A matching B-tree index lets Postgres jump to qualifying rows "
                "instead of checking every page."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=node.relation,
            fix_label="Create supporting index",
            fix_sql=index_sql,
        )
    )


def _like_pattern(node: PlanNode, out: list[Suggestion]) -> None:
    blob = " ".join(filter(None, [node.filter, node.index_cond, node.join_filter]))
    if not blob:
        return
    leading_wildcard = bool(
        re.search(r"~~\*?\s+'%", blob) or re.search(r"'%[^']*%'", blob)
    )
    if not leading_wildcard:
        return
    relation = node.relation or "your_table"
    cols = _columns_from(blob) or ["search_column"]
    col = cols[0]
    out.append(
        Suggestion(
            id=f"trgm-{node.id}",
            severity="high",
            title=f"Leading-wildcard search on {relation}",
            detail=(
                "ILIKE/LIKE with a leading '%' cannot use a normal B-tree index; "
                f"Postgres falls back to a scan of {relation}. A trigram GIN index "
                "can accelerate substring matches."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=relation,
            fix_label="Add pg_trgm GIN index",
            fix_sql=(
                "CREATE EXTENSION IF NOT EXISTS pg_trgm;\n"
                f"CREATE INDEX idx_{relation}_{col}_trgm "
                f"ON {relation} USING gin ({col} gin_trgm_ops);"
            ),
        )
    )


def _nested_loop(node: PlanNode, out: list[Suggestion]) -> None:
    if node.node_type != "Nested Loop":
        return
    loops = node.actual_loops or 1
    inner = node.children[1] if len(node.children) > 1 else None
    if not inner:
        return
    inner_scan = inner.node_type in {"Seq Scan", "Nested Loop"}
    expensive = node.exclusive_cost_pct >= 12 or (inner.actual_rows or 0) * loops >= 50_000
    if not (inner_scan and expensive):
        return
    rel = inner.relation or "inner_table"
    cols = _columns_from(inner.index_cond, inner.filter, inner.hash_cond, node.join_filter)
    out.append(
        Suggestion(
            id=f"nl-{node.id}",
            severity="high",
            title=f"Nested loop re-scans {rel}",
            detail=(
                f"The inner side of this nested loop is a {inner.node_type.lower()} "
                f"on {rel}. Each outer row triggers another pass"
                f"{_cost_clause(node)}. Index the join/filter key so the inner "
                "lookup becomes an index seek."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=rel,
            fix_label="Index the inner join key",
            fix_sql=_index_sql(rel, cols, fallback="/* join / lookup column */"),
        )
    )


def _sort(node: PlanNode, out: list[Suggestion]) -> None:
    if node.node_type != "Sort":
        return
    if node.exclusive_cost_pct < 8 and (node.exclusive_time or 0) < 8:
        return
    keys = node.sort_key or ["/* order by columns */"]
    relation = _guess_relation(node) or "your_table"
    out.append(
        Suggestion(
            id=f"sort-{node.id}",
            severity="medium",
            title="Explicit sort is dominating runtime",
            detail=(
                f"Postgres is sorting on ({', '.join(keys)})"
                f"{_cost_clause(node)}. An index that matches the ORDER BY "
                "(and any equality filters) can return rows pre-ordered and "
                "skip the sort node entirely."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=relation,
            fix_label="Index the sort keys",
            fix_sql=_index_sql(relation, [k.split()[0].strip("()") for k in keys]),
        )
    )


def _row_estimate(node: PlanNode, out: list[Suggestion]) -> None:
    if node.actual_rows is None or node.plan_rows <= 0:
        return
    actual = max(node.actual_rows, 1.0)
    planned = max(node.plan_rows, 1.0)
    ratio = actual / planned
    if 0.05 <= ratio <= 20:
        return
    factor = max(ratio, 1 / ratio)
    direction = "high" if ratio > 1 else "low"
    relation = node.relation or _guess_relation(node)
    target = relation or "the tables in this node"
    out.append(
        Suggestion(
            id=f"stats-{node.id}",
            severity="medium",
            title=f"Row estimate is {factor:.0f}x too {direction} on {node.node_type}",
            detail=(
                f"Planner expected ~{node.plan_rows:,.0f} rows but actually got "
                f"{node.actual_rows:,.0f}. Bad estimates cascade into the wrong "
                "join type and memory grants. Refresh statistics, then re-run."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=relation,
            fix_label="Refresh planner statistics",
            fix_sql=f"ANALYZE {target};" if relation else "ANALYZE;",
        )
    )


def _filter_waste(node: PlanNode, out: list[Suggestion]) -> None:
    removed = node.rows_removed_by_filter
    if not removed or removed < 10_000 or not node.relation:
        return
    cols = _columns_from(node.filter)
    out.append(
        Suggestion(
            id=f"filt-{node.id}",
            severity="medium",
            title=f"{removed:,} rows discarded by filter on {node.relation}",
            detail=(
                f"The scan produced many rows that later failed `{node.filter}`. "
                "Push that predicate into an index so discarded rows are never read."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=node.relation,
            fix_label="Index the filter columns",
            fix_sql=_index_sql(node.relation, cols, fallback="/* filtered column */"),
        )
    )


def _hash_spill(node: PlanNode, out: list[Suggestion]) -> None:
    batches = node.hash_batches
    if not batches or batches <= 1:
        return
    out.append(
        Suggestion(
            id=f"mem-{node.id}",
            severity="medium",
            title=f"{node.node_type} spilled across {batches} batches",
            detail=(
                "The hash table did not fit in work_mem and spilled to disk. "
                "Raise work_mem for this session, or reduce the build-side rows "
                "with a tighter filter / partial index."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=node.relation,
            fix_label="Increase work_mem for this session",
            fix_sql="SET work_mem = '64MB';",
        )
    )


def _cte(node: PlanNode, out: list[Suggestion]) -> None:
    if node.node_type != "CTE Scan":
        return
    out.append(
        Suggestion(
            id=f"cte-{node.id}",
            severity="low",
            title="CTE is materialized",
            detail=(
                "Postgres materialized this WITH clause, so later filters cannot "
                "push down. If the CTE is referenced once, mark it "
                "NOT MATERIALIZED so the planner can inline it."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=node.relation,
            fix_label="Inline the CTE",
            fix_sql="WITH cte_name AS NOT MATERIALIZED (\n  /* original cte body */\n)\nSELECT * FROM cte_name WHERE /* late filter */;",
        )
    )


def _heap_fetches(node: PlanNode, out: list[Suggestion]) -> None:
    if not node.heap_fetches or node.heap_fetches < 5_000:
        return
    relation = node.relation or _guess_relation(node)
    if not relation:
        return
    out.append(
        Suggestion(
            id=f"vac-{node.id}",
            severity="low",
            title=f"Index-only scan still heap-fetched {node.heap_fetches:,} rows",
            detail=(
                f"Visibility map bits on {relation} are stale, so the index-only "
                "scan visits the heap anyway. VACUUM (and autovacuum tuning) "
                "restores true index-only access."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=relation,
            fix_label="Vacuum the table",
            fix_sql=f"VACUUM (ANALYZE) {relation};",
        )
    )


def _high_cost(node: PlanNode, out: list[Suggestion]) -> None:
    if node.exclusive_cost_pct < 30:
        return
    # Access-method nodes already get a more specific hint (or are healthy).
    if node.node_type in {"Seq Scan", "Index Scan", "Index Only Scan", "Bitmap Heap Scan"}:
        return
    out.append(
        Suggestion(
            id=f"hot-{node.id}",
            severity="high",
            title=f"Hot node: {node.node_type} is {node.exclusive_cost_pct:.0f}% of cost",
            detail=(
                f"This {node.node_type.lower()} accounts for most of the plan cost"
                f"{_cost_clause(node)}. Focus here first: fewer rows in, a better "
                "access method, or a rewrite that avoids the operator entirely."
            ),
            node_id=node.id,
            node_type=node.node_type,
            relation=node.relation,
            fix_label="Inspect this node first",
            fix_sql=(
                "-- Rewrite to shrink input rows into this operator\n"
                "-- e.g. tighter WHERE, pre-aggregate, or covering index\n"
                f"-- node: {node.node_type}  relation: {node.relation or '-'}"
            ),
        )
    )


def _columns_from(*blobs: str | None) -> list[str]:
    cols: list[str] = []
    for blob in blobs:
        if not blob:
            continue
        cleaned = _STRINGS.sub(" ", blob)
        for token in _IDENT.findall(cleaned):
            low = token.lower()
            if low in _SKIP_TOKENS or low.startswith("pg_") or len(token) == 1:
                continue
            if token not in cols:
                cols.append(token)
    return cols[:3]


def _prefer_join_cols(cols: list[str]) -> list[str]:
    fks = [col for col in cols if col.endswith("_id") and col.lower() != "id"]
    return fks or cols


def _index_sql(relation: str, cols: Iterable[str], fallback: str | None = None) -> str:
    cleaned = [c.split(".")[-1] for c in cols if c and c != relation]
    if not cleaned:
        col_sql = fallback or "id"
        suffix = "opt"
    else:
        col_sql = ", ".join(cleaned)
        suffix = "_".join(cleaned)
    return f"CREATE INDEX idx_{relation}_{suffix} ON {relation} ({col_sql});"


def _guess_relation(node: PlanNode) -> str | None:
    if node.relation:
        return node.relation
    for child in node.children:
        found = _guess_relation(child)
        if found:
            return found
    return None


def _cost_clause(node: PlanNode) -> str:
    bits = [f"{node.exclusive_cost_pct:.0f}% of plan cost"]
    if node.exclusive_time is not None:
        bits.append(f"{node.exclusive_time:.1f}ms exclusive")
    if node.actual_rows is not None:
        bits.append(f"{node.actual_rows:,.0f} rows")
    return " (" + ", ".join(bits) + ")"
