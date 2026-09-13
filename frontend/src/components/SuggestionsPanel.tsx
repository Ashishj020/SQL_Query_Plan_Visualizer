import { useState } from "react";
import type { Suggestion } from "../types";

export function SuggestionsPanel({
  suggestions,
  highlightId,
  onHighlight,
}: {
  suggestions: Suggestion[];
  highlightId?: string | null;
  onHighlight: (id: string | null) => void;
}) {
  const [copied, setCopied] = useState<string | null>(null);
  const open = suggestions.length > 0;

  return (
    <section className={`drawer glass ${open ? "open" : ""}`}>
      <div className="drawer-head">
        <h2>Optimization suggestions</h2>
        <span className="status">
          {suggestions.length} {suggestions.length === 1 ? "fix" : "fixes"}
        </span>
      </div>
      <div className="cards">
        {suggestions.map((item) => (
          <article
            key={item.id}
            className={`glass card${highlightId && item.node_id === highlightId ? " hot" : ""}`}
            onMouseEnter={() => onHighlight(item.node_id ?? null)}
            onMouseLeave={() => onHighlight(null)}
          >
            <span className={`sev ${item.severity}`}>{item.severity}</span>
            <h3>{item.title}</h3>
            <p>{item.detail}</p>
            <pre className="fix">{item.fix_sql}</pre>
            <button
              className="copy"
              onClick={async () => {
                try {
                  await navigator.clipboard.writeText(item.fix_sql);
                } catch {
                  const field = document.createElement("textarea");
                  field.value = item.fix_sql;
                  document.body.appendChild(field);
                  field.select();
                  document.execCommand("copy");
                  field.remove();
                }
                setCopied(item.id);
                window.setTimeout(() => setCopied((cur) => (cur === item.id ? null : cur)), 1400);
              }}
            >
              {copied === item.id ? "Copied" : `Copy ${item.fix_label.toLowerCase()}`}
            </button>
          </article>
        ))}
      </div>
    </section>
  );
}
