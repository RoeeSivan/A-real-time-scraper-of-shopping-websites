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
import { Currency, formatPrice } from "@/lib/currency";

interface CurrencyContextValue {
  currency: Currency;
  setCurrency: (c: Currency) => void;
  rate: number | null;
  format: (usd: number) => string;
}

const CurrencyContext = createContext<CurrencyContextValue | null>(null);

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function CurrencyProvider({ children }: { children: ReactNode }) {
  const [currency, setCurrency] = useState<Currency>("USD");
  const [rate, setRate] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    fetch(`${API_BASE}/rate?target=ILS`)
      .then((r) => (r.ok ? r.json() : Promise.reject(r.statusText)))
      .then((payload) => {
        if (!cancelled && typeof payload?.rate === "number") {
          setRate(payload.rate);
        }
      })
      .catch(() => {
        // Quietly fall back to USD-only — toggle stays disabled.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const format = useCallback(
    (usd: number) => formatPrice(usd, currency, rate),
    [currency, rate],
  );

  const value = useMemo(
    () => ({ currency, setCurrency, rate, format }),
    [currency, rate, format],
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
