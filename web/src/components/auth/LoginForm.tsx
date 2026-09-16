"use client";

import { type FormEvent, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";

import { FormField } from "@/components/auth/FormField";
import { SubmitButton } from "@/components/auth/SubmitButton";
import { Dashes } from "@/components/marketing/Sheet";
import { ApiError } from "@/lib/api";
import { login, MIN_PASSWORD_LENGTH, MAX_PASSWORD_LENGTH } from "@/lib/auth-api";

type FormError = { field?: "email" | "password"; message: string };

function loginError(error: unknown): FormError {
  if (error instanceof ApiError) {
    switch (error.code) {
      case "invalid_credentials":
        // Never identify which credential failed, including for suspended users.
        return { message: "Invalid email or password" };
      case "rate_limited":
        return {
          message: error.retryAfterSeconds != null
            ? `Too many attempts — try again in ~${error.retryAfterSeconds}s`
            : "Too many attempts — please wait a moment",
        };
      case "validation_error":
        // The API exposes no field locations; email validity is checked locally.
        return { field: "password", message: error.detail };
    }
  }
  return { message: "Something went wrong — please try again" };
}

export function LoginForm() {
  const router = useRouter();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<FormError | null>(null);
  const [pending, setPending] = useState(false);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (pending) return;
    setError(null);

    const emailInput = event.currentTarget.elements.namedItem("email") as HTMLInputElement;
    if (!emailInput.validity.valid) {
      setError({ field: "email", message: "Enter a valid email address" });
      return;
    }
    if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
      setError({
        field: "password",
        message: password.length < MIN_PASSWORD_LENGTH
          ? `Password must be at least ${MIN_PASSWORD_LENGTH} characters`
          : `Password must be at most ${MAX_PASSWORD_LENGTH} characters`,
      });
      return;
    }

    setPending(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (error) {
      setError(loginError(error));
      setPending(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="flex flex-col gap-5">
      <h1 className="ink text-center text-[20px] uppercase tracking-[0.06em]">
        <span className="tall-block tall-block-center">Log in</span>
      </h1>

      <Dashes />

      <FormField
        label="Email"
        type="email"
        name="email"
        autoComplete="email"
        required
        value={email}
        onChange={(event) => {
          setEmail(event.target.value);
          setError(null);
        }}
        error={error?.field === "email" ? error.message : undefined}
      />

      <FormField
        label="Password"
        type="password"
        name="password"
        autoComplete="current-password"
        required
        minLength={MIN_PASSWORD_LENGTH}
        maxLength={MAX_PASSWORD_LENGTH}
        value={password}
        onChange={(event) => {
          setPassword(event.target.value);
          setError(null);
        }}
        error={error?.field === "password" ? error.message : undefined}
      />

      <Link href="/reset-password" className="text-[11px] text-ink underline hover:opacity-70">
        Forgot password?
      </Link>

      {error && !error.field && (
        <p role="alert" className="text-[12px] text-stamp">{error.message}</p>
      )}

      <SubmitButton pending={pending}>[ Log in ]</SubmitButton>

      <p className="text-center text-[11px] text-ink-faded">
        Need an account?{" "}
        <Link href="/signup" className="text-ink underline hover:opacity-70">Sign up</Link>
      </p>
    </form>
  );
}
