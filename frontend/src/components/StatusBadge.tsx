"use client";

import { ScrapeStatus } from "@/lib/types";

interface StatusBadgeProps {
  status: ScrapeStatus;
  isLoading?: boolean;
}

export function StatusBadge({ status, isLoading = false }: StatusBadgeProps) {
  if (isLoading) {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-blue-100 px-3 py-1 text-xs font-medium text-blue-800">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-600 animate-pulse" />
        Loading...
      </span>
    );
  }

  if (status === "success") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full bg-green-100 px-3 py-1 text-xs font-medium text-green-800">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-600" />
        Success
      </span>
    );
  }

  return (
    <span className="inline-flex items-center gap-1 rounded-full bg-red-100 px-3 py-1 text-xs font-medium text-red-800">
      <span className="inline-block h-1.5 w-1.5 rounded-full bg-red-600" />
      Failed
    </span>
  );
}
