"use client";

import { Fragment } from "react";
import { ScrapeResult, TierAttempt } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";

interface ResultRowProps {
  result: ScrapeResult | null;
  isLoading?: boolean;
}

const TABLE_COL_COUNT = 8;

// Map raw orchestrator errors to user-friendly reasons.
function humanReason(error: string | null | undefined): string {
  if (!error) return "Unknown error";
  const lower = error.toLowerCase();
  if (lower.includes("no candidates")) return "No matching listing on this site";
  if (lower.includes("no candidate cleared")) return "No candidate matched the query well enough";
  if (lower.includes("missing title")) return "No matching listing on this site";
  if (lower.includes("low similarity")) return "Found a listing, but it didn't match the query closely";
  if (lower.includes("non-positive price")) return "Site returned a non-positive price";
  if (lower.includes("captcha") || lower.includes("blocked")) return "Site bot-blocked the request";
  if (lower.includes("openai") || lower.includes("llm")) return "AI extraction failed on this site";
  if (lower.includes("firecrawl")) return "External scraper couldn't extract a listing";
  if (lower.includes("all tiers failed")) return "No tier could extract a valid listing";
  return error;
}

function TierBadge({ attempt }: { attempt: TierAttempt }) {
  const ok = attempt.outcome === "succeeded";
  return (
    <span className="font-mono">
      {attempt.tier}{" "}
      <span
        className={ok ? "text-green-600 font-bold" : "text-red-500"}
        title={attempt.error ?? undefined}
      >
        {ok ? "✓" : "✗"}
      </span>
    </span>
  );
}

export function ResultRow({ result, isLoading = false }: ResultRowProps) {
  if (!result && !isLoading) {
    return null;
  }

  const formatPrice = (price: number | null): string => {
    if (price === null) return "N/A";
    return `$${price.toFixed(2)}`;
  };

  const trace = result?.tier_trace ?? [];
  const showTraceStrip = trace.length > 0 || result?.status === "failed";

  return (
    <Fragment>
      <tr className="hover:bg-slate-50">
        <td className="px-4 pt-3 pb-2 text-sm font-medium text-slate-900">
          {result?.site ?? <span className="text-slate-400">—</span>}
        </td>
        <td className="px-4 pt-3 pb-2 text-sm text-slate-700 max-w-xs truncate">
          {result?.title || (isLoading ? <span className="text-slate-400">Loading...</span> : "—")}
        </td>
        <td className="px-4 pt-3 pb-2 text-sm font-semibold text-slate-900">
          {result
            ? result.price !== null
              ? formatPrice(result.price)
              : result.product_url
                ? (
                  <a
                    href={result.product_url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="text-blue-600 hover:text-blue-800 hover:underline font-medium"
                    title="Multi-variant listing — check site for prices"
                  >
                    See variants →
                  </a>
                )
                : "N/A"
            : isLoading
              ? "..."
              : "—"}
        </td>
        <td className="px-4 pt-3 pb-2 text-sm text-slate-700">
          {result?.rating !== null && result?.rating !== undefined ? result.rating.toFixed(1) : (isLoading ? "..." : "—")}
        </td>
        <td className="px-4 pt-3 pb-2 text-sm text-slate-700">
          {result?.review_count !== null && result?.review_count !== undefined ? result.review_count.toLocaleString() : (isLoading ? "..." : "—")}
        </td>
        <td className="px-4 pt-3 pb-2">
          <StatusBadge
            status={result?.status ?? "failed"}
            isLoading={isLoading}
          />
        </td>
        <td className="px-4 pt-3 pb-2 text-sm text-slate-600">
          {result?.method ?? "—"}
        </td>
        <td className="px-4 pt-3 pb-2 text-sm">
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

      {showTraceStrip && (
        <tr className="border-b border-slate-200 bg-slate-50/60">
          <td colSpan={TABLE_COL_COUNT} className="px-4 pb-3 pt-1 text-xs text-slate-500">
            {result?.status === "failed" && result?.error && (
              <span className="mr-3">
                <span className="font-semibold text-slate-600">Reason:</span>{" "}
                <span className="text-slate-700">{humanReason(result.error)}</span>
                {trace.length > 0 && <span className="mx-2 text-slate-300">·</span>}
              </span>
            )}
            {trace.length > 0 && (
              <span>
                <span className="font-semibold text-slate-600">Tier trace:</span>{" "}
                {trace.map((t, i) => (
                  <Fragment key={`${t.tier}-${i}`}>
                    <TierBadge attempt={t} />
                    {i < trace.length - 1 && (
                      <span className="mx-1 text-slate-300">→</span>
                    )}
                  </Fragment>
                ))}
              </span>
            )}
          </td>
        </tr>
      )}
    </Fragment>
  );
}
