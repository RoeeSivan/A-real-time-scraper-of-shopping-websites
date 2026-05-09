export type ScrapeStatus = "success" | "failed";
export type Method = "basic" | "browser" | "llm" | "firecrawl" | "n/a";
export type TierName = "basic" | "browser" | "llm" | "firecrawl";
export type TierOutcome = "succeeded" | "rejected" | "errored";

export interface TierAttempt {
  tier: TierName;
  outcome: TierOutcome;
  error: string | null;
}

export interface ScrapeResult {
  site: string;
  status: ScrapeStatus;
  method: Method;
  title: string | null;
  price: number | null;
  rating: number | null;
  review_count: number | null;
  product_url: string | null;
  similarity: number | null;
  error: string | null;
  tier_trace: TierAttempt[];
}

export interface WishlistEntry {
  query: string;
  savedAt: number;
  lastRunAt: number;
  bestPriceAtSave: number | null;
  bestSiteAtSave: string | null;
  bestPriceNow: number | null;
  bestSiteNow: string | null;
  results: ScrapeResult[];
}
