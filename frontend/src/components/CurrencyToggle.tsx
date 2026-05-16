"use client";

import { useCurrency } from "@/hooks/useCurrency";
import { Currency } from "@/lib/currency";

const OPTIONS: { value: Currency; label: string }[] = [
  { value: "USD", label: "USD $" },
  { value: "ILS", label: "ILS ₪" },
  { value: "EUR", label: "EUR €" },
];

export function CurrencyToggle() {
  const { currency, setCurrency, rates } = useCurrency();

  const activeRate =
    currency === "USD" ? null : (rates[currency] ?? null);
  const activeSymbol =
    currency === "ILS" ? "₪" : currency === "EUR" ? "€" : "";

  return (
    <div className="inline-flex items-center gap-3">
      <div className="inline-flex rounded-full border hairline bg-paper p-0.5 text-xs font-medium">
        {OPTIONS.map((opt) => {
          const active = currency === opt.value;
          const disabled =
            opt.value !== "USD" && rates[opt.value] == null;
          const tooltipRate = opt.value !== "USD" ? rates[opt.value] : null;
          return (
            <button
              key={opt.value}
              type="button"
              onClick={() => !disabled && setCurrency(opt.value)}
              disabled={disabled}
              className={
                "px-3 py-1 rounded-full transition " +
                (active
                  ? "bg-coral text-paper"
                  : "text-muted hover:text-ink disabled:opacity-40 disabled:cursor-not-allowed")
              }
              title={
                disabled
                  ? "Exchange rate unavailable"
                  : tooltipRate != null
                    ? `1 USD = ${tooltipRate.toFixed(2)} ${opt.value}`
                    : undefined
              }
            >
              {opt.label}
            </button>
          );
        })}
      </div>
      {activeRate !== null && (
        <span className="text-[11px] text-muted font-numeric">
          1 USD = {activeRate.toFixed(2)} {activeSymbol}
        </span>
      )}
    </div>
  );
}
