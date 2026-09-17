import Link from "next/link";
import { AuthHeading } from "@/components/auth/AuthHeading";

export default function VerifyEmailPage() {
  return <div className="flex flex-col gap-5 text-[13px] leading-relaxed">
    <AuthHeading>Verify your email</AuthHeading>
    <p>Email verification is now completed during sign up. Older verification links are no longer used.</p>
    <Link href="/signup" className="text-center underline">Continue to sign up</Link>
    <Link href="/login" className="text-center underline">Already have an account? Log in</Link>
  </div>;
}
