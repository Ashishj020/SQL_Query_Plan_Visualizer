export type Severity = "high" | "medium" | "low";

export interface PlanNode {
  id: string;
  node_type: string;
  relation?: string | null;
  alias?: string | null;
  join_type?: string | null;
  startup_cost: number;
  total_cost: number;
  exclusive_cost: number;
  cost_pct: number;
  exclusive_cost_pct: number;
  plan_rows: number;
  actual_startup_time?: number | null;
  actual_total_time?: number | null;
  exclusive_time?: number | null;
  time_pct?: number | null;
  actual_rows?: number | null;
  actual_loops?: number | null;
  filter?: string | null;
  index_cond?: string | null;
  hash_cond?: string | null;
  join_filter?: string | null;
  sort_key?: string[] | null;
  group_key?: string[] | null;
  rows_removed_by_filter?: number | null;
  hash_batches?: number | null;
  peak_memory_kb?: number | null;
  heap_fetches?: number | null;
  children: PlanNode[];
}

export interface Suggestion {
  id: string;
  severity: Severity;
  title: string;
  detail: string;
  node_id?: string | null;
  node_type?: string | null;
  relation?: string | null;
  fix_label: string;
  fix_sql: string;
}

export interface AnalyzeResponse {
  query: string;
  planning_time_ms: number;
  execution_time_ms?: number | null;
  total_cost: number;
  node_count: number;
  plan: PlanNode;
  suggestions: Suggestion[];
}

export interface SampleQuery {
  id: string;
  title: string;
  blurb: string;
  sql: string;
}

export interface HealthResponse {
  ok: boolean;
  database: string;
  postgres_version?: string | null;
  detail?: string | null;
}
