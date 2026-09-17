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
    <div className="flex min-h-screen flex-col items-center bg-background px-5 pt-16 pb-12 text-foreground">
      <Logo className="mb-10" />
      <main className="w-full max-w-[400px]">
        <Sheet className="px-7 py-7 md:px-9">
          <Suspense fallback={<p role="status">Loading your account…</p>}><AccountHome /></Suspense>
        </Sheet>
      </main>
    </div>
  );
}
