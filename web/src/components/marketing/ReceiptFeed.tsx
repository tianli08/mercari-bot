"use client";

import { useEffect, useRef, useState } from "react";

import { Line, Sheet } from "@/components/marketing/Sheet";
import { SAMPLE_FEED } from "@/lib/marketing-content";

const PRINT_EVERY_MS = 2600;
const PRINT_MS = 420;
const FEED_MS = 360;
/** Fixed row height in px: 18px line plus 5px padding each side. */
const ROW_PX = 28;

interface PrintedRow {
  key: number;
  time: string;
  listing: string;
  price: string;
  sold: boolean;
  /** Freshly printed: reveal left to right. */
  printing: boolean;
  /** Feeding out the top of the sheet. */
  leaving: boolean;
}

function formatClock(totalSeconds: number): string {
  const s = ((totalSeconds % 86400) + 86400) % 86400;
  const h = Math.floor(s / 3600);
  const m = Math.floor((s % 3600) / 60);
  return `${String(h).padStart(2, "0")}:${String(m).padStart(2, "0")}`;
}

function startSeconds(): number {
  const [h, m] = SAMPLE_FEED.startTime.split(":").map(Number);
  return h * 3600 + m * 60;
}

/** Build the first `visibleRows` prints, oldest at the top like a real roll. */
function initialRows(): { rows: PrintedRow[]; next: number; clock: number } {
  let clock = startSeconds();
  const rows: PrintedRow[] = [];
  for (let i = 0; i < SAMPLE_FEED.visibleRows; i++) {
    const src = SAMPLE_FEED.rows[i];
    clock += src.gapSeconds;
    rows.push({ key: i, time: formatClock(clock), ...src, printing: false, leaving: false });
  }
  return { rows, next: SAMPLE_FEED.visibleRows, clock };
}

/**
 * The alert feed as a live receipt: every couple of seconds a new alert
 * prints at the bottom with a head sweep, and the roll feeds up so the oldest
 * line leaves through the top. Reduced-motion viewers get a plain swap.
 */
export function ReceiptFeed() {
  const [state, setState] = useState(initialRows);
  const timers = useRef<number[]>([]);

  useEffect(() => {
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const tick = () => {
      setState((prev) => {
        const src = SAMPLE_FEED.rows[prev.next % SAMPLE_FEED.rows.length];
        const clock = prev.clock + src.gapSeconds;
        const fresh: PrintedRow = {
          key: prev.next,
          time: formatClock(clock),
          ...src,
          printing: !reduce,
          leaving: false,
        };
        if (reduce) {
          return { rows: [...prev.rows.slice(1), fresh], next: prev.next + 1, clock };
        }
        const rows = prev.rows.map((r, i) => (i === 0 ? { ...r, leaving: true } : r));
        return { rows: [...rows, fresh], next: prev.next + 1, clock };
      });

      if (!reduce) {
        timers.current.push(
          window.setTimeout(() => {
            setState((prev) => ({
              ...prev,
              rows: prev.rows
                .filter((r) => !r.leaving)
                .map((r) => ({ ...r, printing: false })),
            }));
          }, Math.max(PRINT_MS, FEED_MS) + 40),
        );
      }
    };

    const interval = window.setInterval(tick, PRINT_EVERY_MS);
    const pending = timers.current;
    return () => {
      window.clearInterval(interval);
      pending.forEach((t) => window.clearTimeout(t));
      pending.length = 0;
    };
  }, []);

  return (
    <Sheet className="px-6 pb-5 pt-5 md:px-8">
      <div className="ink flex flex-col gap-1.5 text-[15px]">
        <Line
          left={SAMPLE_FEED.heading}
          right={SAMPLE_FEED.footnote}
          className="text-xs tracking-[0.14em] text-ink-faded"
        />
        <div
          className="flex flex-col justify-end overflow-hidden"
          style={{ height: SAMPLE_FEED.visibleRows * ROW_PX }}
        >
          {state.rows.map((row) => (
            <div
              key={row.key}
              className={`feed-row ${row.leaving ? "feed-row-leaving" : ""} ${row.printing ? "feed-row-printing" : ""}`}
              style={{ "--feed-ms": `${FEED_MS}ms` } as React.CSSProperties}
            >
              <Line
                left={
                  <span
                    className={`block min-w-0 truncate ${row.printing ? "feed-print" : ""}`}
                    style={{ "--print-ms": `${PRINT_MS}ms` } as React.CSSProperties}
                  >
                    {row.time} {row.listing}{" "}
                    {row.sold && (
                      <span
                        className="stamp font-jp text-[12px]"
                        style={{ boxSizing: "border-box", height: 18, lineHeight: "14px", padding: "0 6px", verticalAlign: "top" }}
                      >
                        {SAMPLE_FEED.soldStamp}
                      </span>
                    )}
                  </span>
                }
                right={
                  <span
                    className={`${row.sold ? "line-through" : ""} ${row.printing ? "feed-print feed-print-late" : ""}`}
                    style={{ "--print-ms": `${PRINT_MS}ms` } as React.CSSProperties}
                  >
                    {row.price}
                  </span>
                }
                className={`items-center py-[5px] leading-[18px] ${row.sold ? "text-ink-faded" : ""}`}
              />
            </div>
          ))}
        </div>
      </div>
    </Sheet>
  );
}
