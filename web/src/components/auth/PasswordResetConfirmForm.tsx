"use client";

import { useRef, useState, type FormEvent } from "react";
import { useAuth, useSignIn } from "@clerk/nextjs";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import {
  confirmPasswordReset, hasPasswordResetAttempt, INVALID_CODE, MAX_PASSWORD_LENGTH,
  MIN_PASSWORD_LENGTH, passwordValidationError, recoveryErrorMessage, RESET_CONFIRMATION,
} from "@/lib/auth-recovery";
import { AuthHeading } from "./AuthHeading";
import { FormField } from "./FormField";
import { SubmitButton } from "./SubmitButton";

export function PasswordResetConfirmForm() {
  const { isLoaded, isSignedIn } = useAuth();
  const { signIn } = useSignIn();
  const params = useSearchParams();
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [pending, setPending] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [passwordError, setPasswordError] = useState<string>();
  const [complete, setComplete] = useState(false);
  const submitting = useRef(false);
  const activeAttempt = isLoaded && hasPasswordResetAttempt(signIn);
  const needsPassword = activeAttempt && signIn.status === "needs_new_password";
  const invalidLink = params.has("token") || (!activeAttempt && params.get("requested") !== "1");

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!isLoaded || isSignedIn || invalidLink || complete || submitting.current) return;
    setError(null);
    setPasswordError(undefined);
    if (!activeAttempt) { setError(INVALID_CODE); return; }
    if (needsPassword) {
      const validation = passwordValidationError(password);
      if (validation) { setPasswordError(validation); return; }
    }
    submitting.current = true;
    setPending(true);
    try {
      if (needsPassword) {
        await confirmPasswordReset(signIn, password);
        setPassword("");
        setCode("");
        setComplete(true);
        await signIn.reset();
      } else {
        const result = await signIn.resetPasswordEmailCode.verifyCode({ code: code.trim() });
        if (result.error) throw result.error;
        if (signIn.status !== "needs_new_password") setError(INVALID_CODE);
        else setCode("");
      }
    } catch (error) {
      setError(recoveryErrorMessage(error));
    } finally {
      submitting.current = false;
      setPending(false);
    }
  }

  return <div className="flex flex-col gap-5 text-[13px] leading-relaxed">
    <AuthHeading>{complete ? "Password updated" : needsPassword ? "Choose a new password" : "Reset your password"}</AuthHeading>
    {!isLoaded ? <p role="status">Loading password recovery…</p> : complete ? <>
      <p role="status">Your password has been updated. Log in with your new password.</p>
      <Link href="/login" className="text-center underline">Go to login</Link>
    </> : invalidLink ? <>
      <p role="alert">This reset link is invalid or expired. Request a new code to reset your password.</p>
      <Link href="/reset-password" className="text-center underline">Request a reset code</Link>
    </> : isSignedIn ? <>
      <p>You’re already signed in. Open your profile menu to manage your password.</p>
      <Link href="/dashboard" className="text-center underline">Go to your account</Link>
    </> : <>
      {!needsPassword && <p role="status">{RESET_CONFIRMATION}</p>}
      <form onSubmit={submit} className="flex flex-col gap-5">
        {needsPassword ? <FormField label="New password" type="password" name="password" autoComplete="new-password" required
          minLength={MIN_PASSWORD_LENGTH} maxLength={MAX_PASSWORD_LENGTH} helper={`Use ${MIN_PASSWORD_LENGTH}–${MAX_PASSWORD_LENGTH} characters.`}
          error={passwordError} value={password} onChange={(event) => setPassword(event.target.value)} disabled={pending} />
          : <FormField label="Reset code" name="code" autoComplete="one-time-code" inputMode="numeric" required
            value={code} onChange={(event) => setCode(event.target.value)} disabled={pending} />}
        {error && <p role="alert" className="text-stamp">{error}</p>}
        <SubmitButton pending={pending}>{needsPassword ? "Update password" : "Verify reset code"}</SubmitButton>
      </form>
      <Link href="/reset-password" className="text-center underline">Request a new code</Link>
      <Link href="/login" className="text-center underline">Back to login</Link>
    </>}
  </div>;
}
