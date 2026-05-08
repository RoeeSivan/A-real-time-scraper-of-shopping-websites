"use client";

import { SearchBar } from "@/components/SearchBar";
import { ResultsTable } from "@/components/ResultsTable";
import { useSearch } from "@/hooks/useSearch";

export default function Home() {
  const { results, isSearching, error, search } = useSearch();

  return (
    <main className="min-h-screen flex flex-col items-center gap-8 p-8 bg-slate-50">
      <div className="text-center">
        <h1 className="text-4xl font-bold text-slate-900 mb-2">
          Real-Time Product Scraper
        </h1>
        <p className="text-slate-600 text-base">
          Search across Amazon, BestBuy, Walmart, and Newegg simultaneously
        </p>
      </div>

      <SearchBar onSearch={search} disabled={isSearching} />

      {error && (
        <div className="w-full max-w-6xl rounded-md bg-red-100 px-4 py-3 text-sm text-red-800 border border-red-200">
          <strong>Error:</strong> {error}
        </div>
      )}

      <ResultsTable results={results} isSearching={isSearching} />
    </main>
  );
}
