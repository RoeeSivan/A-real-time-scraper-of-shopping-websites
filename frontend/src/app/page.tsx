"use client";

import { SearchBar } from "@/components/SearchBar";
import { ResultsTable } from "@/components/ResultsTable";
import { PriceChart } from "@/components/PriceChart";
import { useSearch } from "@/hooks/useSearch";

export default function Home() {
  const { results, isSearching, error, search } = useSearch();

  return (
    <main className="min-h-screen flex flex-col items-center px-6 pb-24">
      <div className="w-full max-w-3xl pt-20 pb-10 text-center">
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

      {error && (
        <div className="w-full max-w-3xl mt-6 rounded-md border border-[color:var(--color-coral-soft)] bg-[color:var(--color-coral-soft)]/20 px-4 py-3 text-sm text-[color:var(--color-brick)]">
          <strong className="font-medium">Something went wrong.</strong>{" "}
          {error}
        </div>
      )}

      <div className="w-full max-w-5xl mt-14 space-y-12">
        <PriceChart results={results} />
        <ResultsTable results={results} isSearching={isSearching} />
      </div>
    </main>
  );
}
