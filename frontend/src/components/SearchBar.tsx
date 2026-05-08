"use client";

import { useState } from "react";

interface SearchBarProps {
  onSearch: (query: string) => void;
  disabled?: boolean;
}

export function SearchBar({ onSearch, disabled = false }: SearchBarProps) {
  const [query, setQuery] = useState("");

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (query.trim()) {
      onSearch(query.trim());
    }
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="w-full max-w-xl flex gap-2"
    >
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Search for a product..."
        disabled={disabled}
        className="flex-1 rounded-md border border-slate-300 px-4 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-slate-900 disabled:opacity-50 bg-white"
      />
      <button
        type="submit"
        disabled={disabled || !query.trim()}
        className="rounded-md bg-slate-900 px-4 py-2 text-white text-sm font-medium hover:bg-slate-700 disabled:opacity-50"
      >
        Search
      </button>
    </form>
  );
}
