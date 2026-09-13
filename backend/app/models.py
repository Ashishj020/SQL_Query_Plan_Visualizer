from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field


Severity = Literal["high", "medium", "low"]


class AnalyzeRequest(BaseModel):
    sql: str = Field(..., min_length=6, max_length=20_000)
    analyze: bool = True


class PlanNode(BaseModel):
    id: str
    node_type: str
    relation: Optional[str] = None
    alias: Optional[str] = None
    schema_name: Optional[str] = None
    join_type: Optional[str] = None
    startup_cost: float = 0
    total_cost: float = 0
    exclusive_cost: float = 0
    cost_pct: float = 0
    exclusive_cost_pct: float = 0
    plan_rows: float = 0
    plan_width: Optional[int] = None
    actual_startup_time: Optional[float] = None
    actual_total_time: Optional[float] = None
    exclusive_time: Optional[float] = None
    time_pct: Optional[float] = None
    actual_rows: Optional[float] = None
    actual_loops: Optional[int] = None
    filter: Optional[str] = None
    index_cond: Optional[str] = None
    hash_cond: Optional[str] = None
    join_filter: Optional[str] = None
    rec_check_cond: Optional[str] = None
    sort_key: Optional[list[str]] = None
    group_key: Optional[list[str]] = None
    output: Optional[list[str]] = None
    rows_removed_by_filter: Optional[int] = None
    hash_batches: Optional[int] = None
    peak_memory_kb: Optional[int] = None
    heap_fetches: Optional[int] = None
    workers_planned: Optional[int] = None
    workers_launched: Optional[int] = None
    parallel_aware: Optional[bool] = None
    extra: dict[str, Any] = Field(default_factory=dict)
    children: list[PlanNode] = Field(default_factory=list)


class Suggestion(BaseModel):
    id: str
    severity: Severity
    title: str
    detail: str
    node_id: Optional[str] = None
    node_type: Optional[str] = None
    relation: Optional[str] = None
    fix_label: str
    fix_sql: str


class AnalyzeResponse(BaseModel):
    query: str
    planning_time_ms: float = 0
    execution_time_ms: Optional[float] = None
    total_cost: float = 0
    node_count: int = 0
    plan: PlanNode
    suggestions: list[Suggestion] = Field(default_factory=list)


class SampleQuery(BaseModel):
    id: str
    title: str
    blurb: str
    sql: str


class HealthResponse(BaseModel):
    ok: bool
    database: str
    postgres_version: Optional[str] = None
    detail: Optional[str] = None
