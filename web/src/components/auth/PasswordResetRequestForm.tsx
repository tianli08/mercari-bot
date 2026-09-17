"use client";

import { useRef, useState, type FormEvent } from "react";
import { useAuth, useSignIn } from "@clerk/nextjs";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { requestPasswordReset, recoveryErrorMessage } from "@/lib/auth-recovery";
import { AuthHeading } from "./AuthHeading";
import { FormField } from "./FormField";
import { SubmitButton } from "./SubmitButton";

export function PasswordResetRequestForm() {
  const { isLoaded, isSignedIn } = useAuth();
  const { signIn } = useSignIn();
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isLoaded || isSignedIn || submitting.current) return;
    submitting.current = true;
    setPending(true);
    setError(null);
    try {
      await requestPasswordReset(signIn, email);
      // This flag only selects the uniform inbox notice, never authorizes a reset.
      // It contains no email, password, or token and is identical for every account.
      router.push("/reset-password/confirm?requested=1");
    } catch (error) {
      setError(recoveryErrorMessage(error));
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return <div className="flex flex-col gap-5 text-[13px] leading-relaxed">
    <AuthHeading>Reset your password</AuthHeading>
    {!isLoaded ? <p role="status">Loading password recovery…</p> : isSignedIn ? <>
      <p>You’re already signed in. Open your profile menu to manage your password.</p>
      <Link href="/dashboard" className="text-center underline">Go to your account</Link>
    </> : <>
      <p>Enter your email and we’ll send a code to help you reset your password.</p>
      <form onSubmit={submit} className="flex flex-col gap-5">
        <FormField label="Email" type="email" name="email" autoComplete="email" required
          value={email} onChange={(event) => setEmail(event.target.value)} disabled={pending} />
        {error && <p role="alert" className="text-stamp">{error}</p>}
        <SubmitButton pending={pending}>Send reset code</SubmitButton>
      </form>
      <Link href="/login" className="text-center underline">Back to login</Link>
    </>}
  </div>;
}
