import type { Metadata } from "next";

import { PRODUCT_NAME } from "@/lib/marketing-content";
import { SignupForm } from "@/components/auth/SignupForm";

export const metadata: Metadata = {
  title: `Sign up — ${PRODUCT_NAME}`,
};

export default function SignupPage() {
  return <SignupForm />;
}
