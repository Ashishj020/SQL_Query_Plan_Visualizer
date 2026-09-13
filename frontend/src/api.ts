import type { AnalyzeResponse, HealthResponse, SampleQuery } from "./types";

async function readError(res: Response): Promise<string> {
  try {
    const body = await res.json();
    return body.detail || res.statusText;
  } catch {
    return res.statusText;
  }
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch("/api/health");
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function fetchSamples(): Promise<SampleQuery[]> {
  const res = await fetch("/api/samples");
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}

export async function analyzeQuery(sql: string): Promise<AnalyzeResponse> {
  const res = await fetch("/api/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ sql, analyze: true }),
  });
  if (!res.ok) throw new Error(await readError(res));
  return res.json();
}
