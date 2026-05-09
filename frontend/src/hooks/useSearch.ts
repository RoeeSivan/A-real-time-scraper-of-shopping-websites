"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ScrapeResult } from "@/lib/types";
import { startSSEStream } from "@/lib/sse";

interface UseSearchState {
  results: ScrapeResult[];
  isSearching: boolean;
  error: string | null;
  query: string;
}

const API_BASE = process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";

export function useSearch() {
  const [state, setState] = useState<UseSearchState>({
    results: [],
    isSearching: false,
    error: null,
    query: "",
  });

  const eventSourceRef = useRef<EventSource | null>(null);

  const search = useCallback((query: string) => {
    // Clean up any existing connection
    if (eventSourceRef.current) {
      eventSourceRef.current.close();
    }

    // Reset state
    setState({
      results: [],
      isSearching: true,
      error: null,
      query,
    });

    // Start SSE stream
    const eventSource = startSSEStream(query, API_BASE, {
      onResult: (result) => {
        setState((prev) => {
          // Update or add result for this site
          const existingIndex = prev.results.findIndex(
            (r) => r.site === result.site
          );
          if (existingIndex >= 0) {
            const updated = [...prev.results];
            updated[existingIndex] = result;
            return { ...prev, results: updated };
          } else {
            return { ...prev, results: [...prev.results, result] };
          }
        });
      },
      onDone: () => {
        setState((prev) => ({ ...prev, isSearching: false }));
      },
      onError: (error) => {
        setState((prev) => ({
          ...prev,
          isSearching: false,
          error: error.message,
        }));
      },
    });

    eventSourceRef.current = eventSource;
  }, []);

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      if (eventSourceRef.current) {
        eventSourceRef.current.close();
      }
    };
  }, []);

  return { ...state, search };
}
