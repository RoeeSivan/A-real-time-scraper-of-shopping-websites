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
  const url = `${apiBase}/search?q=${encodeURIComponent(query)}`;
  console.log("[sse] opening", url);

  const eventSource = new EventSource(url);
  let receivedDone = false;

  eventSource.addEventListener("open", () => {
    console.log("[sse] open — readyState=", eventSource.readyState);
  });

  eventSource.addEventListener("result", (event) => {
    console.log("[sse] event:result", event.data);
    try {
      const result = JSON.parse(event.data) as ScrapeResult;
      options.onResult?.(result);
    } catch (err) {
      console.error("[sse] failed to parse result:", err);
      options.onError?.(new Error("Failed to parse SSE result"));
    }
  });

  eventSource.addEventListener("done", () => {
    console.log("[sse] event:done");
    receivedDone = true;
    eventSource.close();
    options.onDone?.();
  });

  // EventSource fires "error" both on real connection failures AND after a
  // clean close from the server (right after we receive `done`). Don't
  // surface the post-done close as an error.
  eventSource.addEventListener("error", () => {
    console.log(
      "[sse] error — readyState=",
      eventSource.readyState,
      "receivedDone=",
      receivedDone
    );
    if (receivedDone) return;
    eventSource.close();
    options.onError?.(new Error("SSE connection failed"));
  });

  return eventSource;
}
