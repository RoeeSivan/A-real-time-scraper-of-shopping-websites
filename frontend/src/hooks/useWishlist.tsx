"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";
import { ScrapeResult, WishlistEntry } from "@/lib/types";

const STORAGE_KEY = "pricewise.wishlist";

interface WishlistContextValue {
  entries: WishlistEntry[];
  hasEntry: (query: string) => boolean;
  saveCurrent: (query: string, results: ScrapeResult[]) => void;
  updateFromResults: (query: string, results: ScrapeResult[]) => void;
  remove: (query: string) => void;
  clear: () => void;
}

const WishlistContext = createContext<WishlistContextValue | null>(null);

function cheapestOf(results: ScrapeResult[]): {
  price: number | null;
  site: string | null;
} {
  const priced = results.filter(
    (r): r is ScrapeResult & { price: number } =>
      r.status === "success" && typeof r.price === "number" && r.price > 0,
  );
  if (priced.length === 0) return { price: null, site: null };
  const winner = priced.reduce((a, b) => (a.price < b.price ? a : b));
  return { price: winner.price, site: winner.site };
}

function loadFromStorage(): WishlistEntry[] {
  if (typeof window === "undefined") return [];
  try {
    const raw = window.localStorage.getItem(STORAGE_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? (parsed as WishlistEntry[]) : [];
  } catch {
    return [];
  }
}

function saveToStorage(entries: WishlistEntry[]): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(entries));
  } catch (err) {
    console.warn("wishlist: localStorage write failed", err);
  }
}

export function WishlistProvider({ children }: { children: ReactNode }) {
  const [entries, setEntries] = useState<WishlistEntry[]>([]);
  const [hydrated, setHydrated] = useState(false);

  // Hydrate once on mount; SSR safe. setState here is intentional — we
  // can't read localStorage during render without breaking SSR/hydration.
  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setEntries(loadFromStorage());
    // eslint-disable-next-line react-hooks/set-state-in-effect
    setHydrated(true);
  }, []);

  // Persist on every change after hydration (skip the initial empty state
  // to avoid clobbering existing storage before hydration completes).
  useEffect(() => {
    if (!hydrated) return;
    saveToStorage(entries);
  }, [entries, hydrated]);

  const hasEntry = useCallback(
    (query: string) => entries.some((e) => e.query === query.trim()),
    [entries],
  );

  const saveCurrent = useCallback(
    (query: string, results: ScrapeResult[]) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      setEntries((prev) => {
        if (prev.some((e) => e.query === trimmed)) return prev;
        const { price, site } = cheapestOf(results);
        const now = Date.now();
        const entry: WishlistEntry = {
          query: trimmed,
          savedAt: now,
          lastRunAt: now,
          bestPriceAtSave: price,
          bestSiteAtSave: site,
          bestPriceNow: price,
          bestSiteNow: site,
          results,
        };
        return [entry, ...prev];
      });
    },
    [],
  );

  const updateFromResults = useCallback(
    (query: string, results: ScrapeResult[]) => {
      const trimmed = query.trim();
      if (!trimmed) return;
      setEntries((prev) => {
        const idx = prev.findIndex((e) => e.query === trimmed);
        if (idx === -1) return prev;
        const { price, site } = cheapestOf(results);
        const updated: WishlistEntry = {
          ...prev[idx],
          lastRunAt: Date.now(),
          bestPriceNow: price,
          bestSiteNow: site,
          results,
        };
        const next = [...prev];
        next[idx] = updated;
        return next;
      });
    },
    [],
  );

  const remove = useCallback((query: string) => {
    const trimmed = query.trim();
    setEntries((prev) => prev.filter((e) => e.query !== trimmed));
  }, []);

  const clear = useCallback(() => setEntries([]), []);

  const value = useMemo<WishlistContextValue>(
    () => ({ entries, hasEntry, saveCurrent, updateFromResults, remove, clear }),
    [entries, hasEntry, saveCurrent, updateFromResults, remove, clear],
  );

  return (
    <WishlistContext.Provider value={value}>
      {children}
    </WishlistContext.Provider>
  );
}

export function useWishlist(): WishlistContextValue {
  const ctx = useContext(WishlistContext);
  if (!ctx) {
    throw new Error("useWishlist must be used inside <WishlistProvider>");
  }
  return ctx;
}
