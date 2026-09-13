import * as d3 from "d3";
import { useEffect, useMemo, useRef, useState } from "react";
import { costColor, fmt, nodeBox } from "../costColor";
import type { PlanNode } from "../types";

type PointNode = {
  data: PlanNode;
  x: number;
  y: number;
  w: number;
  h: number;
  hasKids: boolean;
};

function prune(node: PlanNode, collapsed: Set<string>): PlanNode {
  if (collapsed.has(node.id)) return { ...node, children: [] };
  return { ...node, children: node.children.map((child) => prune(child, collapsed)) };
}

function findOriginal(node: PlanNode, id: string): PlanNode | null {
  if (node.id === id) return node;
  for (const child of node.children) {
    const found = findOriginal(child, id);
    if (found) return found;
  }
  return null;
}

export function PlanTree({
  plan,
  highlightId,
  onHover,
}: {
  plan: PlanNode;
  highlightId?: string | null;
  onHover: (node: PlanNode | null, x: number, y: number) => void;
}) {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [collapsed, setCollapsed] = useState<Set<string>>(new Set());
  const [transform, setTransform] = useState<d3.ZoomTransform>(d3.zoomIdentity.translate(48, 80));

  useEffect(() => {
    setCollapsed(new Set());
  }, [plan]);

  useEffect(() => {
    const el = canvasRef.current;
    if (!el) return;
    const z = d3
      .zoom<HTMLDivElement, unknown>()
      .scaleExtent([0.35, 2.4])
      .on("zoom", (event) => setTransform(event.transform));
    const selection = d3.select(el);
    selection.call(z);
    selection.call(z.transform, d3.zoomIdentity.translate(48, 80));
    return () => {
      selection.on(".zoom", null);
    };
  }, [plan.id]);

  const layout = useMemo(() => {
    const visible = prune(plan, collapsed);
    const root = d3.hierarchy(visible);
    d3.tree<PlanNode>().nodeSize([148, 290])(root);
    const nodes: PointNode[] = [];
    const links: { from: PointNode; to: PointNode }[] = [];
    const byId = new Map<string, PointNode>();

    root.descendants().forEach((d) => {
      const box = nodeBox(d.data.exclusive_cost_pct);
      const original = findOriginal(plan, d.data.id);
      const x = d.x ?? 0;
      const y = d.y ?? 0;
      const point: PointNode = {
        data: d.data,
        x: x - box.h / 2,
        y,
        w: box.w,
        h: box.h,
        hasKids: Boolean(original && original.children.length > 0),
      };
      nodes.push(point);
      byId.set(d.data.id, point);
    });

    root.links().forEach((link) => {
      const from = byId.get(link.source.data.id);
      const to = byId.get(link.target.data.id);
      if (from && to) links.push({ from, to });
    });

    return { nodes, links };
  }, [plan, collapsed]);

  return (
    <div
      className="tree-canvas"
      ref={canvasRef}
      onMouseLeave={() => onHover(null, 0, 0)}
    >
      <div
        className="tree-world"
        style={{ transform: `translate(${transform.x}px, ${transform.y}px) scale(${transform.k})` }}
      >
        <svg>
          {layout.links.map((link, i) => {
            const x1 = link.from.y + link.from.w;
            const y1 = link.from.x + link.from.h / 2;
            const x2 = link.to.y;
            const y2 = link.to.x + link.to.h / 2;
            const mid = (x1 + x2) / 2;
            return (
              <path
                key={`${link.from.data.id}-${link.to.data.id}-${i}`}
                className="link"
                d={`M${x1},${y1} C${mid},${y1} ${mid},${y2} ${x2},${y2}`}
                stroke={costColor(link.to.data.exclusive_cost_pct)}
              />
            );
          })}
        </svg>
        {layout.nodes.map((node) => {
          const pct = node.data.exclusive_cost_pct;
          const color = costColor(pct);
          const hot = highlightId === node.data.id;
          return (
            <article
              key={node.data.id}
              className={`glass node${hot ? " hot" : ""}`}
              style={{
                left: node.y,
                top: node.x,
                width: node.w,
                height: node.h,
                borderColor: hot ? color : `${color}aa`,
                background: `linear-gradient(180deg, ${color}55, rgba(10, 14, 24, 0.72))`,
                boxShadow: `0 0 24px ${color}22, 0 0 0 1px ${color}40, inset 0 1px 0 rgba(255,255,255,0.14)`,
              }}
              onMouseMove={(event) => {
                const rect = canvasRef.current?.getBoundingClientRect();
                onHover(
                  node.data,
                  event.clientX - (rect?.left ?? 0) + 18,
                  event.clientY - (rect?.top ?? 0) + 18,
                );
              }}
            >
              <div className="node-head">
                <span className="node-type" style={{ color }}>
                  {node.data.node_type}
                  {node.data.join_type ? ` · ${node.data.join_type}` : ""}
                </span>
                {pct >= 25 && <span className="badge">Hot</span>}
                {node.hasKids && (
                  <button
                    className="chevron"
                    onClick={(event) => {
                      event.stopPropagation();
                      setCollapsed((prev) => {
                        const next = new Set(prev);
                        if (next.has(node.data.id)) next.delete(node.data.id);
                        else next.add(node.data.id);
                        return next;
                      });
                    }}
                  >
                    {collapsed.has(node.data.id) ? "+" : "–"}
                  </button>
                )}
              </div>
              <div className="node-rel">{node.data.relation || node.data.alias || "operator"}</div>
              <div className="cost-bar">
                <span style={{ width: `${Math.max(pct, 4)}%`, background: color }} />
              </div>
              <div className="node-meta">
                <span>{fmt(pct, 0)}% cost</span>
                <span>{fmt(node.data.exclusive_time ?? node.data.actual_total_time)} ms</span>
                <span>{fmt(node.data.actual_rows ?? node.data.plan_rows, 0)} rows</span>
              </div>
            </article>
          );
        })}
      </div>
    </div>
  );
}
