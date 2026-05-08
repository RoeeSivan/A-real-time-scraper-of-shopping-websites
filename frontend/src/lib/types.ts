export type ScrapeStatus = "success" | "failed";
export type Method = "basic" | "browser" | "llm" | "firecrawl" | "n/a";

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
}
