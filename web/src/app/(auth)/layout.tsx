import type { ReactNode } from "react";

import Link from "next/link";
import { Mark } from "@/components/marketing/Logo";
import { PRODUCT_NAME } from "@/lib/marketing-content";

/**
 * Shared layout for all auth screens: centered card with the product
 * wordmark linking home. No external fonts or third-party requests —
 * auth pages stay lean and don't leak tokens via Referer.
 *
 * Server component; interactivity lives in the page-level client
 * components (SignupForm, etc.).
 */
export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center bg-background px-5 pt-16 pb-12">
      {/* Wordmark */}
      <Link
        href="/"
        className="mb-10 inline-flex items-center gap-2.5 text-[11px] uppercase tracking-[0.16em] text-ink hover:opacity-70"
        aria-label={PRODUCT_NAME}
      >
        <Mark size={16} />
        <span>{PRODUCT_NAME}</span>
      </Link>

      {/* Auth card */}
      <div className="sheet relative w-full max-w-[400px] bg-paper-white px-7 py-8 md:px-9">
        {children}
      </div>
    </div>
  );
}
