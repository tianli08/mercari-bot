import type { Metadata } from "next";
import { Suspense } from "react";
import { PasswordResetConfirmForm } from "@/components/auth/PasswordResetConfirmForm";

export const metadata: Metadata = { title: "Choose a new password — Static Archive" };

export default function PasswordRecoveryPage() {
  return <Suspense fallback={<p role="status">Loading password recovery…</p>}>
    <PasswordResetConfirmForm />
  </Suspense>;
}
