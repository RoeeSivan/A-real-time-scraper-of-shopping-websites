import { ScrapeResult } from "./types";

export interface SSEStreamOptions {
  onResult?: (result: ScrapeResult) => void;
  onDone?: () => void;
  onError?: (error: Error) => void;
}

export function startSSEStream(
  query: string,
  apiBase: string,
  options: SSEStreamOptions
): EventSource {
  const eventSource = new EventSource(
    `${apiBase}/search?q=${encodeURIComponent(query)}`
  );

  eventSource.addEventListener("result", (event) => {
    try {
      const result = JSON.parse(event.data) as ScrapeResult;
      options.onResult?.(result);
    } catch (err) {
      console.error("Failed to parse result:", err);
      options.onError?.(
        new Error("Failed to parse SSE result")
      );
    }
  });

  eventSource.addEventListener("done", () => {
    eventSource.close();
    options.onDone?.();
  });

  eventSource.addEventListener("error", () => {
    eventSource.close();
    options.onError?.(new Error("SSE connection failed"));
  });

  return eventSource;
}
