import { useCallback, useEffect, useState } from "react";
import { analyzeQuery, fetchHealth, fetchSamples } from "./api";
import { QueryEditor } from "./components/QueryEditor";
import { PlanTree } from "./components/PlanTree";
import { SuggestionsPanel } from "./components/SuggestionsPanel";
import { fmt } from "./costColor";
import type { AnalyzeResponse, HealthResponse, PlanNode, SampleQuery } from "./types";

const FALLBACK_SQL = `SELECT c.email, o.id, o.total, o.status
FROM customers c
JOIN orders o ON o.customer_id = c.id
WHERE c.email = 'user42@example.com';`;

export default function App() {
  const [sql, setSql] = useState(FALLBACK_SQL);
  const [samples, setSamples] = useState<SampleQuery[]>([]);
  const [activeSample, setActiveSample] = useState<string | null>("unindexed-join");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [result, setResult] = useState<AnalyzeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [hover, setHover] = useState<{ node: PlanNode; x: number; y: number } | null>(null);
  const [highlightId, setHighlightId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const loadHealth = () =>
      fetchHealth()
        .then((info) => {
          if (!cancelled) setHealth(info);
        })
        .catch(() => {
          if (!cancelled) setHealth({ ok: false, database: "disconnected" });
        });
    loadHealth();
    const timer = window.setInterval(loadHealth, 4000);
    fetchSamples()
      .then((items) => {
        setSamples(items);
        const join = items.find((item) => item.id === "unindexed-join");
        if (join) setSql(join.sql);
      })
      .catch(() => undefined);
    return () => {
      cancelled = true;
      window.clearInterval(timer);
    };
  }, []);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    setHover(null);
    try {
      const payload = await analyzeQuery(sql);
      setResult(payload);
    } catch (err) {
      setResult(null);
      setError(err instanceof Error ? err.message : "Analyze failed");
    } finally {
      setLoading(false);
    }
  }, [sql]);

  const version = health?.postgres_version?.split(" ").slice(0, 2).join(" ");

  return (
    <div className="app">
      <header className="topbar glass">
        <div className="brand">
          <span className="diamond" />
          PLANLIGHT
        </div>
        <div className="metrics">
          <Metric label="Execution" value={result ? `${fmt(result.execution_time_ms)} ms` : "—"} />
          <Metric label="Planning" value={result ? `${fmt(result.planning_time_ms)} ms` : "—"} />
          <Metric label="Total cost" value={result ? fmt(result.total_cost, 0) : "—"} />
          <Metric label="Nodes" value={result ? String(result.node_count) : "—"} />
        </div>
        <div className="status-wrap">
          <div className="status glass">
            <span className={`dot${health?.ok ? " ok" : ""}`} />
            {health?.ok ? version || "Postgres connected" : "Postgres offline"}
          </div>
        </div>
      </header>

      <div className="workspace">
        <aside className="sidebar">
          <div className="section-label">
            <span>Query</span>
            <span>{sql.split("\n").length} lines</span>
          </div>
          <QueryEditor value={sql} onChange={setSql} onSubmit={run} />
          <button className="analyze" disabled={loading} onClick={run}>
            {loading ? "Explaining…" : "Analyze plan"}
            <span className="hint">⌘/Ctrl ⏎</span>
          </button>
          <div className="samples">
            {samples.map((sample) => (
              <button
                key={sample.id}
                className={`chip${activeSample === sample.id ? " active" : ""}`}
                title={sample.blurb}
                onClick={() => {
                  setActiveSample(sample.id);
                  setSql(sample.sql);
                }}
              >
                {sample.title}
              </button>
            ))}
          </div>
        </aside>

        <main className="stage">
          <div className="tree-shell">
            {loading && <TreeSkeleton />}
            {!loading && result && (
              <PlanTree
                plan={result.plan}
                highlightId={highlightId}
                onHover={(node, x, y) => setHover(node ? { node, x, y } : null)}
              />
            )}
            {!loading && !result && !error && (
              <div className="empty glass">
                <h2>Drop a query in the well</h2>
                <p>Planlight runs EXPLAIN ANALYZE, paints the tree by cost, and writes the index you’d actually paste.</p>
              </div>
            )}
            {error && (
              <div className="error-banner glass">
                <h2>Couldn’t explain that</h2>
                <p>{error}</p>
              </div>
            )}
            {hover && (
              <div className="tooltip glass" style={{ left: hover.x, top: hover.y }}>
                <h3>{hover.node.node_type}</h3>
                <dl>
                  <dt>Rows</dt>
                  <dd>{fmt(hover.node.actual_rows ?? hover.node.plan_rows, 0)}</dd>
                  <dt>Cost</dt>
                  <dd>{fmt(hover.node.total_cost)}</dd>
                  <dt>Time</dt>
                  <dd>{fmt(hover.node.actual_total_time)} ms</dd>
                  {hover.node.filter && (
                    <>
                      <dt>Filter</dt>
                      <dd>{hover.node.filter}</dd>
                    </>
                  )}
                  {hover.node.actual_loops != null && (
                    <>
                      <dt>Loops</dt>
                      <dd>{hover.node.actual_loops}</dd>
                    </>
                  )}
                </dl>
              </div>
            )}
          </div>
          <SuggestionsPanel
            suggestions={result?.suggestions ?? []}
            highlightId={highlightId}
            onHighlight={setHighlightId}
          />
        </main>
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric glass">
      <label>{label}</label>
      <strong>{value}</strong>
    </div>
  );
}

function TreeSkeleton() {
  return (
    <div className="skeleton">
      {[
        { l: 40, t: 120, w: 210 },
        { l: 320, t: 40, w: 240 },
        { l: 320, t: 210, w: 220 },
        { l: 620, t: 90, w: 200 },
      ].map((box, i) => (
        <div
          key={i}
          className="glass skel-node"
          style={{ left: box.l, top: box.t, width: box.w, height: 96 }}
        />
      ))}
    </div>
  );
}
