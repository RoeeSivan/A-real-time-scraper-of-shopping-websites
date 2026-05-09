"use client";

import { ScrapeResult } from "@/lib/types";
import { ResultRow } from "./ResultRow";

// Must match the `name` field on each SiteConfig in backend/app/sites/*.py.
const SITES = ["Amazon.com", "BestBuy.com", "Walmart.com", "Newegg.com"];

interface ResultsTableProps {
  results: ScrapeResult[];
  isSearching: boolean;
}

export function ResultsTable({ results, isSearching }: ResultsTableProps) {
  if (!isSearching && results.length === 0) {
    return null;
  }

  const resultMap = new Map(results.map((r) => [r.site, r]));

  return (
    <section className="w-full">
      <div className="flex items-baseline justify-between mb-4 px-1">
        <h2 className="font-display italic text-2xl text-ink">Results</h2>
        <span className="text-xs uppercase tracking-[0.25em] text-muted">
          four stores
        </span>
      </div>
      <div className="w-full overflow-x-auto rounded-xl border hairline bg-paper">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b hairline">
              {[
                "Store",
                "Product",
                "Price",
                "Rating",
                "Reviews",
                "Status",
                "Method",
                "",
              ].map((label) => (
                <th
                  key={label}
                  className="px-5 py-3 text-left text-[10px] font-medium uppercase tracking-[0.18em] text-muted"
                >
                  {label}
                </th>
              ))}
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
    </section>
  );
}
