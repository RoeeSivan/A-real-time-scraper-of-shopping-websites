"use client";

import { ScrapeStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: ScrapeStatus;
  isLoading?: boolean;
}

export function StatusBadge({ status, isLoading = false }: StatusBadgeProps) {
  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs text-muted">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-muted/60 animate-pulse" />
        <span className="tracking-wide">searching…</span>
      </span>
    );
  }

  if (status === "success") {
    return (
      <span className="inline-flex items-center gap-1.5 text-xs font-medium text-sage">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-sage" />
        Found
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1.5 text-xs font-medium text-[color:var(--color-brick)]">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-[color:var(--color-brick)]/70" />
      No match
    </span>
  );
}
