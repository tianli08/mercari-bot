import Link from "next/link";
import { AuthHeading } from "@/components/auth/AuthHeading";

export default function PasswordRecoveryPage() {
  return <div className="flex flex-col gap-5 text-[13px] leading-relaxed">
    <AuthHeading>Reset your password</AuthHeading>
    <p>Open the login page, enter your email, then choose “Forgot password?” to reset your password securely.</p>
    <Link href="/login" className="text-center underline">Go to login</Link>
  </div>;
}
