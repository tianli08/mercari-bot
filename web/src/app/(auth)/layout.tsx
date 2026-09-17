import type { ReactNode } from "react";
import type { Metadata } from "next";

import { Logo } from "@/components/marketing/Logo";
import { Sheet } from "@/components/marketing/Sheet";

export const metadata: Metadata = {
  referrer: "no-referrer",
  robots: { index: false, follow: false },
};

export default function AuthLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen flex-col items-center bg-background px-5 pt-16 pb-12 text-foreground selection:bg-ink selection:text-paper-white">
      <Logo className="mb-10" />

      <main className="w-full max-w-[400px]">
        <Sheet className="px-7 py-7 md:px-9">{children}</Sheet>
      </main>
    </div>
  );
}
