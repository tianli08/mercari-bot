import Link from "next/link";

import { PRODUCT_NAME } from "@/lib/marketing-content";

/** The glitch-block mark: three bands, the middle one slipped. Inherits `currentColor`. */
export function Mark({ size = 18, className = "" }: { size?: number; className?: string }) {
  return (
    <svg
      viewBox="0 0 100 100"
      width={size}
      height={size}
      className={className}
      aria-hidden
      focusable="false"
    >
      <g fill="currentColor">
        <rect x="10" y="10" width="68" height="24" />
        <rect x="22" y="38" width="68" height="24" />
        <rect x="10" y="66" width="68" height="24" />
      </g>
    </svg>
  );
}

/** Mark plus wordmark, linking home. Text stays live for accessibility. */
export function Logo({
  size = 18,
  className = "",
  href = "/",
}: {
  size?: number;
  className?: string;
  href?: string;
}) {
  return (
    <Link
      href={href}
      className={`inline-flex items-center gap-2.5 text-[11px] uppercase tracking-[0.16em] hover:opacity-70 ${className}`}
      aria-label={PRODUCT_NAME}
    >
      <Mark size={size} />
      <span>{PRODUCT_NAME}</span>
    </Link>
  );
}
