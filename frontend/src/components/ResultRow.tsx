"use client";

import { Fragment } from "react";
import { ScrapeResult, TierAttempt } from "@/lib/types";
import { StatusBadge } from "./StatusBadge";
import { useCurrency } from "@/hooks/useCurrency";

interface ResultRowProps {
  result: ScrapeResult | null;
  isLoading?: boolean;
}

const TABLE_COL_COUNT = 8;

function humanReason(error: string | null | undefined): string {
  if (!error) return "Unknown error";
  const lower = error.toLowerCase();
  // Cases where every tier ran cleanly but no real listing was found —
  // most often the site genuinely doesn't carry the queried product.
  if (lower.includes("missing title")) return "Site doesn't appear to carry this product";
  if (lower.includes("empty extraction")) return "Site doesn't appear to carry this product";
  if (lower.includes("no candidates")) return "Site doesn't appear to carry this product";
  if (lower.includes("no candidate cleared")) return "No candidate matched the query well enough";
  if (lower.includes("low similarity")) return "Found a listing, but it didn't match the query closely";
  if (lower.includes("non-positive price")) return "Site returned a non-positive price";
  if (lower.includes("captcha") || lower.includes("blocked")) return "Site bot-blocked the request";
  if (lower.includes("payment required")) return "Firecrawl out of credits";
  if (lower.includes("openai") || lower.includes("llm")) return "AI extraction failed on this site";
  if (lower.includes("firecrawl")) return "External scraper couldn't extract a listing";
  if (lower.includes("all tiers failed")) return "No tier could extract a valid listing";
  return error;
}

function TierBadge({ attempt }: { attempt: TierAttempt }) {
  const ok = attempt.outcome === "succeeded";
  return (
    <span className="font-numeric">
      {attempt.tier}{" "}
      <span
        className={ok ? "text-sage font-semibold" : "text-[color:var(--color-brick)]/80"}
        title={attempt.error ?? undefined}
      >
        {ok ? "✓" : "✗"}
      </span>
    </span>
  );
}

function Skeleton({ width = "w-20" }: { width?: string }) {
  return (
    <span
      className={`inline-block h-3 ${width} rounded bg-[color:var(--color-hairline)] animate-pulse`}
    />
  );
}

export function ResultRow({ result, isLoading = false }: ResultRowProps) {
  const { format } = useCurrency();

  if (!result && !isLoading) {
    return null;
  }

  const formatPrice = (price: number | null): string => {
    if (price === null) return "N/A";
    return format(price);
  };

  const trace = result?.tier_trace ?? [];
  const showTraceStrip = trace.length > 0 || result?.status === "failed";

  return (
    <Fragment>
      <tr className="border-b hairline last:border-b-0 hover:bg-cream/60 transition-colors">
        <td className="px-5 pt-4 pb-3 text-sm font-medium text-ink whitespace-nowrap">
          {result?.site ?? <span className="text-muted/60">—</span>}
        </td>
        <td className="px-5 pt-4 pb-3 max-w-xs">
          {result?.title ? (
            <span className="font-display italic text-[15px] text-ink leading-snug line-clamp-2">
              {result.title}
            </span>
          ) : isLoading ? (
            <Skeleton width="w-48" />
          ) : (
            <span className="text-muted/60">—</span>
          )}
        </td>
        <td className="px-5 pt-4 pb-3 text-sm font-numeric font-medium text-ink whitespace-nowrap">
          {result ? (
            result.price !== null ? (
              formatPrice(result.price)
            ) : result.product_url ? (
              <a
                href={result.product_url}
                target="_blank"
                rel="noopener noreferrer"
                className="text-coral hover:text-[color:var(--color-brick)] underline-offset-4 hover:underline"
                title="Multi-variant listing — check site for prices"
              >
                See variants →
              </a>
            ) : (
              <span className="text-muted/60">—</span>
            )
          ) : isLoading ? (
            <Skeleton width="w-14" />
          ) : (
            <span className="text-muted/60">—</span>
          )}
        </td>
        <td className="px-5 pt-4 pb-3 text-sm text-ink whitespace-nowrap">
          {result?.rating !== null && result?.rating !== undefined ? (
            <span className="inline-flex items-baseline gap-1">
              <span className="text-coral">★</span>
              <span className="font-numeric">{result.rating.toFixed(1)}</span>
            </span>
          ) : isLoading ? (
            <Skeleton width="w-10" />
          ) : (
            <span className="text-muted/60">—</span>
          )}
        </td>
        <td className="px-5 pt-4 pb-3 text-sm text-muted font-numeric whitespace-nowrap">
          {result?.review_count !== null && result?.review_count !== undefined ? (
            result.review_count.toLocaleString()
          ) : isLoading ? (
            <Skeleton width="w-12" />
          ) : (
            <span className="text-muted/60">—</span>
          )}
        </td>
        <td className="px-5 pt-4 pb-3 whitespace-nowrap">
          <StatusBadge
            status={result?.status ?? "failed"}
            isLoading={isLoading}
          />
        </td>
        <td className="px-5 pt-4 pb-3 text-xs text-muted font-numeric whitespace-nowrap">
          {result?.method && result.method !== "n/a" ? result.method : "—"}
        </td>
        <td className="px-5 pt-4 pb-3 text-sm whitespace-nowrap">
          {result?.product_url ? (
            <a
              href={result.product_url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-coral hover:text-[color:var(--color-brick)] transition-colors"
              aria-label="Open product page"
            >
              View →
            </a>
          ) : (
            <span className="text-muted/60">—</span>
          )}
        </td>
      </tr>

      {showTraceStrip && (
        <tr className="border-b hairline last:border-b-0 bg-cream/40">
          <td
            colSpan={TABLE_COL_COUNT}
            className="px-5 pb-3 pt-1 text-xs text-muted"
          >
            {result?.status === "failed" && result?.error && (
              <span className="mr-3">
                <span className="font-medium text-ink/80">Reason:</span>{" "}
                <span>{humanReason(result.error)}</span>
                {trace.length > 0 && (
                  <span className="mx-2 text-muted/40">·</span>
                )}
              </span>
            )}
            {trace.length > 0 && (
              <span>
                <span className="font-medium text-ink/80">Tier trace:</span>{" "}
                {trace.map((t, i) => (
                  <Fragment key={`${t.tier}-${i}`}>
                    <TierBadge attempt={t} />
                    {i < trace.length - 1 && (
                      <span className="mx-1 text-muted/40">→</span>
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
