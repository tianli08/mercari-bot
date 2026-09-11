import type { ReactNode } from "react";

import type { PaperTint } from "@/lib/marketing-content";

const TINT_CLASS: Record<PaperTint, string> = {
  white: "bg-paper-white",
  grey: "bg-paper-grey",
  pink: "bg-paper-pink",
};

export function tintClass(tint: PaperTint): string {
  return TINT_CLASS[tint];
}

/** A receipt scanned flat on the bed: paper tint, grain, edge, glare. */
export function Sheet({
  tint = "white",
  className = "",
  children,
}: {
  tint?: PaperTint;
  className?: string;
  children: ReactNode;
}) {
  return <div className={`sheet ${TINT_CLASS[tint]} ${className}`}>{children}</div>;
}

/** One left/right line of receipt print. */
export function Line({
  left,
  right,
  className = "",
}: {
  left: ReactNode;
  right?: ReactNode;
  className?: string;
}) {
  return (
    <div className={`flex justify-between gap-3 ${className}`}>
      <span>{left}</span>
      {right !== undefined && <span className="whitespace-nowrap">{right}</span>}
    </div>
  );
}

export function Dashes({ double = false }: { double?: boolean }) {
  return (
    <div className="dashes text-sm" aria-hidden>
      {double ? "=".repeat(80) : "- ".repeat(48)}
    </div>
  );
}

export function Barcode({ value, className = "" }: { value: string; className?: string }) {
  return (
    <div
      className={`font-barcode max-w-full overflow-hidden text-center leading-none text-ink ${className}`}
      aria-hidden
    >
      {value}
    </div>
  );
}
