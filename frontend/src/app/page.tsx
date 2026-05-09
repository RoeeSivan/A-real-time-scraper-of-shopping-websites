"use client";

import { useEffect, useState } from "react";
import { SearchBar } from "@/components/SearchBar";
import { ResultsTable } from "@/components/ResultsTable";
import { PriceChart } from "@/components/PriceChart";
import { CurrencyToggle } from "@/components/CurrencyToggle";
import { WishlistButton } from "@/components/WishlistButton";
import { WishlistDrawer } from "@/components/WishlistDrawer";
import { CurrencyProvider } from "@/hooks/useCurrency";
import { WishlistProvider, useWishlist } from "@/hooks/useWishlist";
import { useSearch } from "@/hooks/useSearch";

function HomeInner() {
  const { results, isSearching, error, query, search } = useSearch();
  const { hasEntry, updateFromResults } = useWishlist();
  const [drawerOpen, setDrawerOpen] = useState(false);

  // After a re-run completes, refresh the saved entry's bestPriceNow + results.
  useEffect(() => {
    if (isSearching) return;
    const trimmed = query.trim();
    if (!trimmed || results.length === 0) return;
    if (!hasEntry(trimmed)) return;
    updateFromResults(trimmed, results);
    // We intentionally only re-run when the search lifecycle flips from
    // searching → idle for this query — depending on `results` length too
    // would fire on every SSE delta.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isSearching]);

  const handleReRun = (q: string) => {
    setDrawerOpen(false);
    search(q);
  };

  const showSaveButton = !isSearching && results.length > 0 && query.trim().length > 0;

  return (
    <main className="min-h-screen flex flex-col items-center px-6 pb-24">
      <div className="w-full max-w-5xl pt-6 flex justify-end">
        <WishlistButton variant="header" onOpen={() => setDrawerOpen(true)} />
      </div>

      <div className="w-full max-w-3xl pt-12 pb-10 text-center">
        <p className="text-xs uppercase tracking-[0.3em] text-muted mb-5">
          A calmer price comparison
        </p>
        <h1 className="text-6xl md:text-7xl font-display text-ink leading-[1.05]">
          Price<span className="italic text-coral">wise</span>
        </h1>
        <p className="mt-5 text-base text-muted max-w-lg mx-auto">
          Search once. We&rsquo;ll quietly check Amazon, Best Buy, Walmart,
          and Newegg, and bring back the best matches we can find.
        </p>
      </div>

      <SearchBar onSearch={search} disabled={isSearching} />

      <div className="w-full max-w-2xl mt-4 flex justify-end">
        <CurrencyToggle />
      </div>

      {error && (
        <div className="w-full max-w-3xl mt-6 rounded-md border border-[color:var(--color-coral-soft)] bg-[color:var(--color-coral-soft)]/20 px-4 py-3 text-sm text-[color:var(--color-brick)]">
          <strong className="font-medium">Something went wrong.</strong>{" "}
          {error}
        </div>
      )}

      <div className="w-full max-w-5xl mt-14 space-y-6">
        {showSaveButton && (
          <div className="flex justify-end">
            <WishlistButton
              variant="save-current"
              query={query}
              results={results}
            />
          </div>
        )}
        <PriceChart results={results} />
        <ResultsTable results={results} isSearching={isSearching} />
      </div>

      <WishlistDrawer
        open={drawerOpen}
        onClose={() => setDrawerOpen(false)}
        onReRun={handleReRun}
      />
    </main>
  );
}

export default function Home() {
  return (
    <CurrencyProvider>
      <WishlistProvider>
        <HomeInner />
      </WishlistProvider>
    </CurrencyProvider>
  );
}
