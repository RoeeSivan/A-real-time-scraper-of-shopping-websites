"use client";

import { ScrapeResult } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

interface ResultRowProps {
  result: ScrapeResult | null;
  isLoading?: boolean;
}

export function ResultRow({ result, isLoading = false }: ResultRowProps) {
  if (!result && !isLoading) {
    return null;
  }

  const formatPrice = (price: number | null): string => {
    if (price === null) return "N/A";
    return `$${price.toFixed(2)}`;
  };

  return (
    <tr className="border-b border-slate-200 hover:bg-slate-50">
      <td className="px-4 py-3 text-sm font-medium text-slate-900">
        {result?.site ?? <span className="text-slate-400">—</span>}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700 max-w-xs truncate">
        {result?.title || (isLoading ? <span className="text-slate-400">Loading...</span> : "—")}
      </td>
      <td className="px-4 py-3 text-sm font-semibold text-slate-900">
        {result ? formatPrice(result.price) : (isLoading ? "..." : "—")}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {result?.rating !== null && result?.rating !== undefined ? result.rating.toFixed(1) : (isLoading ? "..." : "—")}
      </td>
      <td className="px-4 py-3 text-sm text-slate-700">
        {result?.review_count !== null && result?.review_count !== undefined ? result.review_count.toLocaleString() : (isLoading ? "..." : "—")}
      </td>
      <td className="px-4 py-3">
        <StatusBadge
          status={result?.status ?? "failed"}
          isLoading={isLoading}
        />
      </td>
      <td className="px-4 py-3 text-sm text-slate-600">
        {result?.method ?? "—"}
      </td>
      <td className="px-4 py-3 text-sm">
        {result?.product_url ? (
          <a
            href={result.product_url}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 hover:underline"
          >
            View →
          </a>
        ) : (
          <span className="text-slate-400">—</span>
        )}
      </td>
    </tr>
  );
}
