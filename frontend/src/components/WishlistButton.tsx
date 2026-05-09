"use client";

import { useWishlist } from "@/hooks/useWishlist";
import { ScrapeResult } from "@/lib/types";

interface HeaderProps {
  variant: "header";
  onOpen: () => void;
}

interface SaveCurrentProps {
  variant: "save-current";
  query: string;
  results: ScrapeResult[];
}

type WishlistButtonProps = HeaderProps | SaveCurrentProps;

export function WishlistButton(props: WishlistButtonProps) {
  const { entries, hasEntry, saveCurrent } = useWishlist();

  if (props.variant === "header") {
    const count = entries.length;
    return (
      <button
        type="button"
        onClick={props.onOpen}
        className="inline-flex items-center gap-2 rounded-full border hairline bg-paper px-3 py-1 text-xs font-medium text-muted hover:text-coral transition"
        aria-label={`Open saved searches (${count})`}
      >
        <span>♥</span>
        <span>Saved ({count})</span>
      </button>
    );
  }

  const trimmed = props.query.trim();
  const saved = trimmed.length > 0 && hasEntry(trimmed);
  const disabled = trimmed.length === 0 || saved;

  return (
    <button
      type="button"
      onClick={() => saveCurrent(trimmed, props.results)}
      disabled={disabled}
      className={
        "inline-flex items-center gap-2 rounded-full border px-3 py-1 text-xs font-medium transition " +
        (saved
          ? "border-[color:var(--color-sage)]/30 bg-paper text-sage cursor-default"
          : "hairline bg-paper text-coral hover:bg-[color:var(--color-coral-soft)]/20")
      }
      title={saved ? "Already in your wishlist" : "Save this search"}
    >
      <span>{saved ? "♥" : "♡"}</span>
      <span>{saved ? "Saved" : "Save this search"}</span>
    </button>
  );
}
