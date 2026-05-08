"use client";

import { useState } from "react";

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

type HealthResponse = {
  status: string;
  openai_configured: boolean;
  firecrawl_configured: boolean;
};

export default function Home() {
  const [result, setResult] = useState<HealthResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function checkHealth() {
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      const res = await fetch(`${API_BASE}/health`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setResult((await res.json()) as HealthResponse);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Unknown error");
    } finally {
      setLoading(false);
    }
  }

  return (
    <main className="min-h-screen flex flex-col items-center justify-center gap-6 p-8 bg-slate-50">
      <h1 className="text-2xl font-semibold text-slate-800">
        Real-Time Product Scraper
      </h1>
      <p className="text-slate-600 text-sm">
        Foundation check &mdash; click to verify the FastAPI backend.
      </p>

      <button
        onClick={checkHealth}
        disabled={loading}
        className="rounded-md bg-slate-900 px-4 py-2 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
      >
        {loading ? "Checking..." : "Check backend /health"}
      </button>

      {error && (
        <div className="rounded-md bg-red-100 px-4 py-2 text-sm text-red-800">
          Error: {error}
        </div>
      )}

      {result && (
        <pre className="rounded-md bg-white border border-slate-200 px-4 py-3 text-xs text-slate-800 shadow-sm">
{JSON.stringify(result, null, 2)}
        </pre>
      )}
    </main>
  );
}
