import type { Metadata } from "next";
import { Suspense } from "react";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { Logo } from "@/components/marketing/Logo";
import { PRODUCT_NAME } from "@/lib/marketing-content";

export const metadata: Metadata = {
  title: `Your dashboard — ${PRODUCT_NAME}`,
  robots: { index: false, follow: false },
};

export default function DashboardPage() {
  return (
    <div className="min-h-svh bg-background px-5 py-8 text-foreground sm:px-8 sm:py-12">
      <div className="mx-auto w-full max-w-6xl">
        <header className="mb-10 border-b border-dashed border-ink/30 pb-6"><Logo /></header>
        <main className="min-w-0">
          <div className="mb-8 space-y-2">
            <h1 className="text-[28px] uppercase tracking-[0.06em] sm:text-[36px]">Your dashboard</h1>
            <p className="text-[13px] text-ink-dim">Your saved connections and watchlists.</p>
          </div>
          <Suspense fallback={<p role="status" className="text-[13px] text-ink-dim">Loading your account…</p>}>
            <DashboardShell />
          </Suspense>
        </main>
      </div>
    </div>
  );
}
