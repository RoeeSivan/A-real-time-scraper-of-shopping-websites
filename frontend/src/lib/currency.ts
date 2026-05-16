export type Currency = "USD" | "ILS" | "EUR";

export const SYMBOL: Record<Currency, string> = {
  USD: "$",
  ILS: "₪",
  EUR: "€",
};

export type Rates = Partial<Record<Currency, number>>;

export function formatPrice(
  usd: number,
  currency: Currency,
  rates: Rates,
): string {
  if (currency === "USD") {
    return `${SYMBOL.USD}${usd.toFixed(2)}`;
  }
  const rate = rates[currency];
  if (rate == null) {
    return `${SYMBOL.USD}${usd.toFixed(2)}`;
  }
  return `${SYMBOL[currency]}${(usd * rate).toFixed(2)}`;
}
