from __future__ import annotations

from typing import Any, Optional

from .models import PlanNode

_PASSTHROUGH_SKIP = {
    "Node Type",
    "Parent Relationship",
    "Plans",
    "Relation Name",
    "Schema",
    "Alias",
    "Join Type",
    "Startup Cost",
    "Total Cost",
    "Plan Rows",
    "Plan Width",
    "Actual Startup Time",
    "Actual Total Time",
    "Actual Rows",
    "Actual Loops",
    "Filter",
    "Index Cond",
    "Hash Cond",
    "Join Filter",
    "Recheck Cond",
    "Sort Key",
    "Group Key",
    "Output",
    "Rows Removed by Filter",
    "Hash Batches",
    "Peak Memory Usage",
    "Heap Fetches",
    "Workers Planned",
    "Workers Launched",
    "Parallel Aware",
}


class PlanParseError(ValueError):
    pass


def parse_explain_json(payload: Any) -> tuple[PlanNode, float, Optional[float]]:
    if isinstance(payload, list):
        if not payload:
            raise PlanParseError("EXPLAIN returned an empty result.")
        payload = payload[0]
    if not isinstance(payload, dict) or "Plan" not in payload:
        raise PlanParseError("Unexpected EXPLAIN JSON shape.")

    counter = {"n": 0}
    root = _from_raw(payload["Plan"], counter)
    _annotate_costs(root)
    planning = float(payload.get("Planning Time") or 0)
    execution = payload.get("Execution Time")
    execution_ms = float(execution) if execution is not None else None
    return root, planning, execution_ms


def count_nodes(node: PlanNode) -> int:
    return 1 + sum(count_nodes(child) for child in node.children)


def _from_raw(raw: dict[str, Any], counter: dict[str, int]) -> PlanNode:
    counter["n"] += 1
    extra = {k: v for k, v in raw.items() if k not in _PASSTHROUGH_SKIP}
    children = [_from_raw(child, counter) for child in raw.get("Plans") or []]
    return PlanNode(
        id=f"n{counter['n']}",
        node_type=raw.get("Node Type") or "Unknown",
        relation=raw.get("Relation Name"),
        alias=raw.get("Alias"),
        schema_name=raw.get("Schema"),
        join_type=raw.get("Join Type"),
        startup_cost=float(raw.get("Startup Cost") or 0),
        total_cost=float(raw.get("Total Cost") or 0),
        plan_rows=float(raw.get("Plan Rows") or 0),
        plan_width=raw.get("Plan Width"),
        actual_startup_time=_maybe_float(raw.get("Actual Startup Time")),
        actual_total_time=_maybe_float(raw.get("Actual Total Time")),
        actual_rows=_maybe_float(raw.get("Actual Rows")),
        actual_loops=_maybe_int(raw.get("Actual Loops")),
        filter=raw.get("Filter"),
        index_cond=raw.get("Index Cond"),
        hash_cond=raw.get("Hash Cond"),
        join_filter=raw.get("Join Filter"),
        rec_check_cond=raw.get("Recheck Cond"),
        sort_key=_as_str_list(raw.get("Sort Key")),
        group_key=_as_str_list(raw.get("Group Key")),
        output=_as_str_list(raw.get("Output")),
        rows_removed_by_filter=_maybe_int(raw.get("Rows Removed by Filter")),
        hash_batches=_maybe_int(raw.get("Hash Batches")),
        peak_memory_kb=_maybe_int(raw.get("Peak Memory Usage")),
        heap_fetches=_maybe_int(raw.get("Heap Fetches")),
        workers_planned=_maybe_int(raw.get("Workers Planned")),
        workers_launched=_maybe_int(raw.get("Workers Launched")),
        parallel_aware=raw.get("Parallel Aware"),
        extra=extra,
        children=children,
    )


def _annotate_costs(root: PlanNode) -> None:
    def walk(node: PlanNode) -> None:
        for child in node.children:
            walk(child)
        child_cost = sum(child.total_cost for child in node.children)
        node.exclusive_cost = max(node.total_cost - child_cost, 0.0)
        inclusive_time = _inclusive_time(node)
        child_time = sum(_inclusive_time(child) or 0.0 for child in node.children)
        if inclusive_time is not None:
            node.exclusive_time = max(inclusive_time - child_time, 0.0)

    walk(root)
    total_cost = root.total_cost or 1.0
    total_time = _inclusive_time(root) or 0.0

    def percents(node: PlanNode) -> None:
        node.cost_pct = 100.0 * node.total_cost / total_cost
        node.exclusive_cost_pct = 100.0 * node.exclusive_cost / total_cost
        if total_time and node.exclusive_time is not None:
            node.time_pct = 100.0 * node.exclusive_time / total_time
        for child in node.children:
            percents(child)

    percents(root)


def _inclusive_time(node: PlanNode) -> Optional[float]:
    if node.actual_total_time is None:
        return None
    loops = node.actual_loops or 1
    return node.actual_total_time * loops


def _maybe_float(value: Any) -> Optional[float]:
    if value is None:
        return None
    return float(value)


def _maybe_int(value: Any) -> Optional[int]:
    if value is None:
        return None
    return int(value)


def _as_str_list(value: Any) -> Optional[list[str]]:
    if value is None:
        return None
    if isinstance(value, list):
        return [str(item) for item in value]
    return [str(value)]
