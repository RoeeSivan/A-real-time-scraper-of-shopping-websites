export type Currency = "USD" | "ILS";

const SYMBOL: Record<Currency, string> = {
  USD: "$",
  ILS: "₪",
};

export function formatPrice(
  usd: number,
  currency: Currency,
  ilsPerUsd: number | null,
): string {
  if (currency === "ILS" && ilsPerUsd !== null) {
    return `${SYMBOL.ILS}${(usd * ilsPerUsd).toFixed(2)}`;
  }
  return `${SYMBOL.USD}${usd.toFixed(2)}`;
}
