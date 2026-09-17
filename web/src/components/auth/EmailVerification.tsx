"use client";

import { useRef, useState, type FormEvent } from "react";
import { useUser } from "@clerk/nextjs";
import type { EmailAddressResource } from "@clerk/nextjs/types";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { INVALID_CODE, recoveryErrorMessage } from "@/lib/auth-recovery";
import { AuthHeading } from "./AuthHeading";
import { FormField } from "./FormField";
import { SubmitButton } from "./SubmitButton";

function VerifyAddress({ email }: { email: EmailAddressResource }) {
  const [code, setCode] = useState("");
  const [sent, setSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const submitting = useRef(false);

  async function act(action: "send" | "verify") {
    if (submitting.current) return;
    submitting.current = true;
    setPending(true);
    setError(null);
    try {
      if (action === "send") {
        await email.prepareVerification({ strategy: "email_code" });
        setSent(true);
        setCode("");
      } else {
        const result = await email.attemptVerification({ code: code.trim() });
        if (result.verification.status === "verified") { setVerified(true); setCode(""); }
        else setError(INVALID_CODE);
      }
    } catch (error) {
      setError(recoveryErrorMessage(error));
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void act(sent ? "verify" : "send");
  }

  if (verified || email.verification.status === "verified") return <>
    <p role="status">Your email is verified.</p>
    <Link href="/dashboard" className="text-center underline">Continue to your account</Link>
  </>;

  return <>
    <p>{sent ? "Check your inbox. We sent a verification code to " : "Send a verification code to "}<span className="break-all">{email.emailAddress}</span>.</p>
    <form onSubmit={submit} className="flex flex-col gap-5">
      {sent && <FormField label="Verification code" name="code" autoComplete="one-time-code" inputMode="numeric" required
        value={code} onChange={(event) => setCode(event.target.value)} disabled={pending} />}
      {error && <p role="alert" className="text-stamp">{error}</p>}
      <SubmitButton pending={pending}>{sent ? "Verify email" : "Send verification code"}</SubmitButton>
    </form>
    {sent && <button type="button" disabled={pending} onClick={() => void act("send")}
      className="text-center underline disabled:opacity-50">Resend code</button>}
  </>;
}

export function EmailVerification() {
  const { isLoaded, user } = useUser();
  const legacyLink = useSearchParams().has("token");
  const email = user?.primaryEmailAddress;

  return <div className="flex flex-col gap-5 text-[13px] leading-relaxed">
    <AuthHeading>Verify your email</AuthHeading>
    {legacyLink && <p role="alert">This verification link is invalid or expired. Continue below to verify your email.</p>}
    {!isLoaded ? <p role="status">Loading email verification…</p> : email ? <VerifyAddress key={email.id} email={email} /> : user ? <>
      <p>Add an email address through your profile menu to verify it.</p>
      <Link href="/dashboard" className="text-center underline">Go to your account</Link>
    </> : <>
      <p>Finish signing up to verify your email with the code in your inbox. You can request a new code during sign up.</p>
      <Link href="/signup" className="text-center underline">Continue sign up</Link>
      <Link href="/login" className="text-center underline">Already have an account? Log in to verify your email</Link>
    </>}
  </div>;
}
