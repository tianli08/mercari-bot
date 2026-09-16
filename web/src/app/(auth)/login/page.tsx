import type { Metadata } from "next";

import { LoginForm } from "@/components/auth/LoginForm";
import { PRODUCT_NAME } from "@/lib/marketing-content";

export const metadata: Metadata = {
  title: `Log in — ${PRODUCT_NAME}`,
};

export default function LoginPage() {
  return <LoginForm />;
}
