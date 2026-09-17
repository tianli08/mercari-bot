import type { Metadata } from "next";
import { Suspense } from "react";
import { AccountHome } from "@/components/auth/AccountHome";
import { Logo } from "@/components/marketing/Logo";
import { Sheet } from "@/components/marketing/Sheet";
import { PRODUCT_NAME } from "@/lib/marketing-content";

export const metadata: Metadata = {
  title: `Your account — ${PRODUCT_NAME}`,
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return (
    <div className="flex min-h-svh flex-col items-center justify-center gap-8 bg-background px-5 py-12 text-foreground">
      <Logo />
      <main className="w-full max-w-[400px]">
        <Sheet className="px-6 py-8 sm:px-9 sm:py-10">
          <Suspense fallback={<p role="status" className="text-center text-[13px] text-ink-dim">Loading your account…</p>}><AccountHome /></Suspense>
        </Sheet>
      </main>
    </div>
  );
}
