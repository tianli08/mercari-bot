import Link from "next/link";

import { PRODUCT_NAME } from "@/lib/marketing-content";

/**
 * The glitch-block mark: three bands, the middle one slipped. Inherits
 * `currentColor`. At 24px and below the gaps widen so the bands stay
 * separate; the geometry is otherwise identical.
 */
export function Mark({ size = 18, className = "" }: { size?: number; className?: string }) {
  const small = size <= 24;
  const h = small ? 22 : 24;
  const ys = small ? [10, 39, 68] : [10, 38, 66];
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
        <rect x="10" y={ys[0]} width="68" height={h} />
        <rect x="22" y={ys[1]} width="68" height={h} />
        <rect x="10" y={ys[2]} width="68" height={h} />
      </g>
    </svg>
  );
}

/** Mark plus wordmark, linking home. Text stays live for accessibility. */
export function Logo({
  size = 13,
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
