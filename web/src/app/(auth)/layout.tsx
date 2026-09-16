import type { ReactNode } from "react";

import { Logo } from "@/components/marketing/Logo";
import { Sheet } from "@/components/marketing/Sheet";
import { RedirectIfAuthenticated } from "@/components/auth/RedirectIfAuthenticated";

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
    <div className="flex min-h-screen flex-col items-center bg-background px-5 pt-16 pb-12 text-foreground selection:bg-ink selection:text-paper-white">
      <RedirectIfAuthenticated />
      <Logo className="mb-10" />

      <main className="w-full max-w-[400px]">
        <Sheet className="px-7 py-7 md:px-9">{children}</Sheet>
      </main>
    </div>
  );
}
