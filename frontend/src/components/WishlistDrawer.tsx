"use client";

import { useEffect } from "react";
import { useWishlist } from "@/hooks/useWishlist";
import { useCurrency } from "@/hooks/useCurrency";
import { WishlistEntry } from "@/lib/types";

interface WishlistDrawerProps {
  open: boolean;
  onClose: () => void;
  onReRun: (query: string) => void;
}

function relativeTime(ts: number): string {
  const diff = Math.max(0, Date.now() - ts);
  const m = Math.floor(diff / 60_000);
  if (m < 1) return "just now";
  if (m < 60) return `${m} min ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h} hr ago`;
  const d = Math.floor(h / 24);
  if (d < 7) return `${d} day${d === 1 ? "" : "s"} ago`;
  const w = Math.floor(d / 7);
  if (w < 5) return `${w} wk${w === 1 ? "" : "s"} ago`;
  return new Date(ts).toLocaleDateString();
}

function DeltaBadge({ entry }: { entry: WishlistEntry }) {
  const { format } = useCurrency();
  const saved = entry.bestPriceAtSave;
  const now = entry.bestPriceNow;
  if (saved === null || now === null) return null;
  const diff = now - saved;
  if (Math.abs(diff) < 0.01) return null;
  const cheaper = diff < 0;
  return (
    <span
      className={
        "inline-flex items-center gap-1 text-xs font-numeric " +
        (cheaper ? "text-sage" : "text-[color:var(--color-brick)]")
      }
      title={`Saved at ${format(saved)}`}
    >
      <span>{cheaper ? "↓" : "↑"}</span>
      <span>
        {format(Math.abs(diff))} since saved
      </span>
    </span>
  );
}

function WishlistRow({
  entry,
  onReRun,
  onRemove,
}: {
  entry: WishlistEntry;
  onReRun: (query: string) => void;
  onRemove: (query: string) => void;
}) {
  const { format } = useCurrency();
  const price = entry.bestPriceNow;
  const site = entry.bestSiteNow;

  return (
    <li className="border-b hairline last:border-b-0 py-5 px-6">
      <h3 className="font-display italic text-xl text-ink leading-snug break-words">
        {entry.query}
      </h3>

      <div className="mt-2 flex items-baseline gap-3 flex-wrap">
        {price !== null ? (
          <span className="font-numeric text-base text-ink">
            {format(price)}
            {site && (
              <span className="text-muted text-sm"> · {site}</span>
            )}
          </span>
        ) : (
          <span className="text-sm text-muted">No price recorded</span>
        )}
        <DeltaBadge entry={entry} />
      </div>

      <p className="mt-1 text-xs text-muted">
        Saved {relativeTime(entry.savedAt)}
        {entry.lastRunAt !== entry.savedAt && (
          <> · re-ran {relativeTime(entry.lastRunAt)}</>
        )}
      </p>

      <div className="mt-3 flex gap-3">
        <button
          type="button"
          onClick={() => onReRun(entry.query)}
          className="rounded-full bg-coral text-paper px-3 py-1 text-xs font-medium hover:bg-[color:var(--color-brick)] transition"
        >
          Re-run
        </button>
        <button
          type="button"
          onClick={() => onRemove(entry.query)}
          className="rounded-full border hairline bg-paper px-3 py-1 text-xs font-medium text-muted hover:text-[color:var(--color-brick)] transition"
        >
          Remove
        </button>
      </div>
    </li>
  );
}

export function WishlistDrawer({ open, onClose, onReRun }: WishlistDrawerProps) {
  const { entries, remove } = useWishlist();

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") onClose();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50"
      role="dialog"
      aria-modal="true"
      aria-label="Saved searches"
    >
      <div
        className="absolute inset-0 bg-ink/30 backdrop-blur-[1px] transition-opacity"
        onClick={onClose}
      />
      <aside className="absolute top-0 right-0 h-full w-full max-w-[420px] bg-cream border-l hairline shadow-xl flex flex-col">
        <header className="flex items-center justify-between px-6 py-5 border-b hairline">
          <h2 className="font-display italic text-2xl text-ink">
            Saved searches
          </h2>
          <button
            type="button"
            onClick={onClose}
            className="text-muted hover:text-ink text-xl leading-none"
            aria-label="Close saved searches"
          >
            ✕
          </button>
        </header>

        {entries.length === 0 ? (
          <div className="flex-1 flex items-center justify-center px-8 text-center">
            <p className="text-sm text-muted">
              No saved searches yet.
              <br />
              Run a search and tap{" "}
              <span className="text-coral">♡ Save this search</span> to keep it
              for later.
            </p>
          </div>
        ) : (
          <ul className="flex-1 overflow-y-auto">
            {entries.map((entry) => (
              <WishlistRow
                key={entry.query}
                entry={entry}
                onReRun={onReRun}
                onRemove={remove}
              />
            ))}
          </ul>
        )}
      </aside>
    </div>
  );
}
