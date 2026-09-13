import { scaleLinear } from "d3";

export const costColor = scaleLinear<string>()
  .domain([0, 16, 38, 100])
  .range(["#2dd4bf", "#5eead4", "#fbbf24", "#fb7185"])
  .clamp(true);

export function nodeBox(pct: number) {
  const t = Math.sqrt(Math.max(pct, 5) / 100);
  return { w: 178 + t * 108, h: 94 + t * 42 };
}

export function fmt(n?: number | null, digits = 1) {
  if (n == null || Number.isNaN(n)) return "—";
  if (Math.abs(n) >= 1000) return n.toLocaleString(undefined, { maximumFractionDigits: 0 });
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}
