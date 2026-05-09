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
      className="w-full max-w-2xl flex items-stretch gap-3 rounded-xl border hairline bg-paper px-2 py-2 shadow-[0_1px_0_rgba(0,0,0,0.03)] focus-within:border-coral/40 focus-within:shadow-[0_0_0_4px_rgba(199,93,63,0.08)] transition"
    >
      <input
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        placeholder="Try “Sony WH-1000XM5 headphones”…"
        disabled={disabled}
        className="flex-1 bg-transparent px-3 py-2 text-base text-ink placeholder:text-muted/70 focus:outline-none disabled:opacity-50"
      />
      <button
        type="submit"
        disabled={disabled || !query.trim()}
        className="rounded-lg bg-coral px-5 py-2 text-sm font-medium text-paper hover:bg-[color:var(--color-brick)] active:scale-[0.98] disabled:opacity-40 disabled:cursor-not-allowed transition"
      >
        {disabled ? "Searching…" : "Search"}
      </button>
    </form>
  );
}
