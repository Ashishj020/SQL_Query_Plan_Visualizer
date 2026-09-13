from __future__ import annotations

import json
from typing import Any

import psycopg
from psycopg.rows import dict_row

from .config import settings
from .models import AnalyzeResponse
from .advisor import advise
from .parser import count_nodes, parse_explain_json
from .security import sanitize_sql


def analyze_sql(raw_sql: str, *, run_analyze: bool = True) -> AnalyzeResponse:
    sql = sanitize_sql(raw_sql)
    options = "ANALYZE, BUFFERS, FORMAT JSON" if run_analyze else "BUFFERS, FORMAT JSON"
    explain_sql = f"EXPLAIN ({options})\n{sql}"

    with psycopg.connect(settings.database_url, autocommit=True) as conn:
        with conn.cursor(row_factory=dict_row) as cur:
            cur.execute("SET default_transaction_read_only = on")
            cur.execute(f"SET statement_timeout = '{settings.statement_timeout_ms}'")
            cur.execute(explain_sql)
            row = cur.fetchone()
            if not row:
                raise RuntimeError("EXPLAIN returned no rows.")
            payload: Any = next(iter(row.values()))
            if isinstance(payload, str):
                payload = json.loads(payload)

    plan, planning_ms, execution_ms = parse_explain_json(payload)
    return AnalyzeResponse(
        query=sql,
        planning_time_ms=planning_ms,
        execution_time_ms=execution_ms,
        total_cost=plan.total_cost,
        node_count=count_nodes(plan),
        plan=plan,
        suggestions=advise(plan),
    )


def health() -> dict[str, Any]:
    try:
        with psycopg.connect(settings.database_url, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute("SELECT version()")
                version = cur.fetchone()[0]
        return {"ok": True, "database": "connected", "postgres_version": version}
    except Exception as exc:  # noqa: BLE001 — surface connect errors to the UI
        return {"ok": False, "database": "disconnected", "detail": str(exc)}
