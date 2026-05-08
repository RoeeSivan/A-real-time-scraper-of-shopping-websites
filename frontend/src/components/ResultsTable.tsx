"use client";

import { ScrapeResult } from "@/lib/types";
import { ResultRow } from "./ResultRow";

const SITES = ["amazon", "bestbuy", "walmart", "newegg"];

interface ResultsTableProps {
  results: ScrapeResult[];
  isSearching: boolean;
}

export function ResultsTable({
  results,
  isSearching,
}: ResultsTableProps) {
  if (!isSearching && results.length === 0) {
    return null;
  }

  // Create a map of site -> result for efficient lookup
  const resultMap = new Map(results.map((r) => [r.site, r]));

  return (
    <div className="w-full max-w-6xl rounded-lg border border-slate-200 bg-white shadow-sm overflow-hidden">
      <table className="w-full border-collapse text-sm">
        <thead className="bg-slate-100 border-b border-slate-200">
          <tr>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Website
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Product Title
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Price
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Average Rating
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Review Count
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Status
            </th>
            <th className="px-4 py-3 text-left font-semibold text-slate-900">
              Method
            </th>
          </tr>
        </thead>
        <tbody>
          {SITES.map((site) => (
            <ResultRow
              key={site}
              result={resultMap.get(site) ?? null}
              isLoading={isSearching && !resultMap.has(site)}
            />
          ))}
        </tbody>
      </table>
    </div>
  );
}
