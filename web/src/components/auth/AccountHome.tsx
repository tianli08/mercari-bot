"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { SignOutButton, UserButton, useAuth, useUser } from "@clerk/nextjs";
import { getCurrentUser, type PublicUser } from "@/lib/auth-api";
import { ApiError } from "@/lib/api";
import { AuthHeading } from "./AuthHeading";

const hasApplicationApi = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL?.trim());

export function AccountHome() {
  const { isLoaded, userId, getToken } = useAuth();
  const { user: clerkUser } = useUser();
  const welcome = useSearchParams().get("welcome") === "1";
  const [account, setAccount] = useState<PublicUser | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!hasApplicationApi || !isLoaded || !userId) return;
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

  return <div className="flex min-w-0 flex-col gap-6 text-center text-[13px] leading-relaxed">
    <div className="flex min-w-0 flex-col gap-4">
      <AuthHeading>Your account</AuthHeading>
    </div>
    <div className="flex min-w-0 flex-col items-center gap-3">
      <div className="flex size-11 items-center justify-center">
        <UserButton appearance={{ elements: { avatarBox: "size-11" } }} />
      </div>
      <p className="w-full text-ink-dim">
        <span className="block">Signed in as</span>
        <span className="mt-1 block text-ink [overflow-wrap:anywhere]">{clerkUser?.primaryEmailAddress?.emailAddress}</span>
      </p>
    </div>
    {error ? <div className="flex flex-col gap-4">
      <p role="alert" className="text-[13px] text-stamp">{error}</p>
      <button type="button" onClick={() => window.location.reload()} className="min-h-11 self-center px-4 underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">Try again</button>
    </div> : account || (!hasApplicationApi && isLoaded && userId) ? <>
      {welcome && <p role="status" className="text-[13px] text-ink-dim">{account ? "Your account is ready." : "You’re signed in."}</p>}
      <p className="text-[13px] text-ink-dim">Use your profile menu to manage your email, password, and signed-in devices.</p>
    </> : <p role="status" className="text-[13px] text-ink-dim">Loading your account…</p>}
    <SignOutButton redirectUrl="/login">
      <button type="button" className="min-h-11 w-full border border-ink/25 px-4 py-2 text-ink transition-colors hover:border-ink/50 hover:bg-ink/5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">Log out</button>
    </SignOutButton>
  </div>;
}
