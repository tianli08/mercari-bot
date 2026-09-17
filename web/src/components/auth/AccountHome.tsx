"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { SignOutButton, UserButton, useAuth, useUser } from "@clerk/nextjs";
import { getCurrentUser, type PublicUser } from "@/lib/auth-api";
import { ApiError } from "@/lib/api";
import { AuthHeading } from "./AuthHeading";

export function AccountHome() {
  const { isLoaded, userId, getToken } = useAuth();
  const { user: clerkUser } = useUser();
  const welcome = useSearchParams().get("welcome") === "1";
  const [account, setAccount] = useState<PublicUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!isLoaded || !userId) return;
    let cancelled = false;
    async function loadAccount() {
      try {
        const token = await getToken();
        if (!token) throw new Error("Session unavailable");
        const user = await getCurrentUser(token);
        if (!cancelled) setAccount(user);
      } catch (error) {
        if (!cancelled) setError(error instanceof ApiError && [401, 403].includes(error.status)
          ? "This account cannot access the application. Complete email verification or sign in with your existing account."
          : "We couldn’t load your account. Please try again.");
      }
    }
    void loadAccount();
    return () => { cancelled = true; };
  }, [isLoaded, userId, getToken]);

  return <div className="flex flex-col gap-5">
    <div className="flex items-center justify-between gap-4">
      <AuthHeading>Your account</AuthHeading>
      <UserButton />
    </div>
    <p className="text-[13px] text-ink-dim">Signed in as <span className="break-all text-ink">{clerkUser?.primaryEmailAddress?.emailAddress}</span></p>
    {error ? <div className="flex flex-col gap-4">
      <p role="alert" className="text-[13px] text-stamp">{error}</p>
      <button type="button" onClick={() => window.location.reload()} className="text-[13px] underline">Try again</button>
    </div> : account ? <>
      {welcome && <p role="status" className="text-[13px] text-ink-dim">Your account is ready.</p>}
      <p className="text-[13px] text-ink-dim">Use your profile menu to manage your email, password, and signed-in devices.</p>
    </> : <p role="status" className="text-[13px] text-ink-dim">Loading your account…</p>}
    <SignOutButton redirectUrl="/login">
      <button type="button" className="text-[13px] underline">Log out</button>
    </SignOutButton>
  </div>;
}
