import type { Metadata } from "next";
import { PasswordResetRequestForm } from "@/components/auth/PasswordResetRequestForm";

export const metadata: Metadata = { title: "Reset your password — Static Archive" };

export default function PasswordRecoveryPage() {
  return <PasswordResetRequestForm />;
}
