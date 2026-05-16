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
import { Currency, Rates, formatPrice } from "@/lib/currency";

interface CurrencyContextValue {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  rates: Rates;
  format: (usd: number) => string;
}

const CurrencyContext = createContext<CurrencyContextValue | null>(null);

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

const FETCH_TARGETS: Exclude<Currency, "USD">[] = ["ILS", "EUR"];

async function fetchRate(target: string): Promise<[string, number] | null> {
  try {
    const resp = await fetch(`${API_BASE}/rate?target=${target}`);
    if (!resp.ok) return null;
    const payload = await resp.json();
    if (typeof payload?.rate === "number") {
      return [target, payload.rate];
    }
  } catch {
    // Swallow — toggle for that currency stays disabled.
  }
  return null;
}

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrency] = useState<Currency>("USD");
  const [rates, setRates] = useState<Rates>({});

  useEffect(() => {
    let cancelled = false;
    Promise.all(FETCH_TARGETS.map(fetchRate)).then((pairs) => {
      if (cancelled) return;
      const next: Rates = {};
      for (const pair of pairs) {
        if (pair) next[pair[0] as Currency] = pair[1];
      }
      setRates(next);
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const format = useCallback(
    (usd: number) => formatPrice(usd, currency, rates),
    [currency, rates],
  );

  const value = useMemo(
    () => ({ currency, setCurrency, rates, format }),
    [currency, rates, format],
  );

  return (
    <CurrencyContext.Provider value={value}>
      {children}
    </CurrencyContext.Provider>
  );
}

export function useCurrency(): CurrencyContextValue {
  const ctx = useContext(CurrencyContext);
  if (!ctx) {
    throw new Error("useCurrency must be used inside <CurrencyProvider>");
  }
  return ctx;
}
