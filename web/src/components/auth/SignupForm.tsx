"use client";

import { type FormEvent, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

import { ApiError } from "@/lib/api";
import { signup, MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH } from "@/lib/auth-api";
import { FormField } from "@/components/auth/FormField";
import { SubmitButton } from "@/components/auth/SubmitButton";
import { Dashes } from "@/components/marketing/Sheet";

/** Maps API error codes to user-facing inline messages. */
function errorMessage(error: ApiError): string {
  switch (error.code) {
    case "email_exists":
      // The message itself includes a login link; the JSX below renders it.
      return "email_exists";
    case "validation_error":
      return error.detail;
    case "rate_limited": {
      const seconds = error.retryAfterSeconds;
      return seconds != null
        ? `Too many attempts — try again in ~${seconds}s`
        : "Too many attempts — please wait a moment";
    }
    default:
      return "Something went wrong — please try again";
  }
}

export function SignupForm() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fieldError, setFieldError] = useState<{ field?: "email" | "password"; message: string } | null>(null);
  const [pending, setPending] = useState(false);

  function clearError() {
    if (fieldError) setFieldError(null);
  }

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();

    // Client-side password bounds validation — catch before the request.
    if (password.length < MIN_PASSWORD_LENGTH) {
      setFieldError({
        field: "password",
        message: `Password must be at least ${MIN_PASSWORD_LENGTH} characters`,
      });
      return;
    }
    if (password.length > MAX_PASSWORD_LENGTH) {
      setFieldError({
        field: "password",
        message: `Password must be at most ${MAX_PASSWORD_LENGTH} characters`,
      });
      return;
    }

    setPending(true);
    try {
      await signup(email, password);
      // Cookie is already set (signup logs you in). Navigate to dashboard.
      router.push("/dashboard");
    } catch (err) {
      setPending(false);
      if (err instanceof ApiError) {
        const msg = errorMessage(err);
        if (err.code === "email_exists") {
          setFieldError({ field: "email", message: msg });
        } else if (err.code === "validation_error") {
          // Validation errors from the server are most likely password-related
          // since email format is caught by the browser.
          setFieldError({ field: "password", message: msg });
        } else {
          setFieldError({ message: msg });
        }
      } else {
        setFieldError({ message: "Something went wrong — please try again" });
      }
    }
  }

  const isEmailExists = fieldError?.field === "email" && fieldError.message === "email_exists";

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      <h1 className="ink text-center text-[20px] uppercase tracking-[0.06em]">
        <span className="tall-block tall-block-center">Sign up</span>
      </h1>

      <Dashes />

      <FormField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        required
        value={email}
        onChange={(e) => {
          setEmail(e.target.value);
          clearError();
        }}
        error={
          fieldError?.field === "email"
            ? isEmailExists
              ? undefined // rendered separately below for the link
              : fieldError.message
            : undefined
        }
      />

      {/* Special rendering for email_exists: includes a link to /login */}
      {isEmailExists && (
        <p role="alert" className="-mt-3 text-[12px] text-stamp">
          An account with this email already exists.{" "}
          <Link href="/login" className="underline hover:opacity-70">
            Log in instead
          </Link>
        </p>
      )}

      <FormField
        label="Password"
        type="password"
        name="password"
        autoComplete="new-password"
        required
        minLength={MIN_PASSWORD_LENGTH}
        maxLength={MAX_PASSWORD_LENGTH}
        value={password}
        onChange={(e) => {
          setPassword(e.target.value);
          clearError();
        }}
        helper={`${MIN_PASSWORD_LENGTH} characters minimum`}
        error={fieldError?.field === "password" ? fieldError.message : undefined}
      />

      {/* General (non-field) error */}
      {fieldError && !fieldError.field && (
        <p role="alert" className="text-[12px] text-stamp">
          {fieldError.message}
        </p>
      )}

      <SubmitButton pending={pending}>[ Sign up ]</SubmitButton>

      <p className="text-center text-[11px] text-ink-faded">
        Already have an account?{" "}
        <Link href="/login" className="text-ink underline hover:opacity-70">
          Log in
        </Link>
      </p>
    </form>
  );
}
