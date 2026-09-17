import type { Metadata } from "next";
import { Suspense } from "react";
import { EmailVerification } from "@/components/auth/EmailVerification";

export const metadata: Metadata = { title: "Verify your email — Static Archive" };

export default function VerifyEmailPage() {
  return <Suspense fallback={<p role="status">Loading email verification…</p>}>
    <EmailVerification />
  </Suspense>;
}
