"use client";

import { SignOutButton, UserButton, useUser } from "@clerk/nextjs";

/** Profile controls only. The dashboard owns application-account access. */
export function AccountHome() {
  const { user } = useUser();

  return <section aria-labelledby="account-heading" className="flex min-w-0 flex-col gap-5 text-[13px] leading-relaxed">
    <h2 id="account-heading" className="text-[16px] uppercase tracking-[0.08em]">Your account</h2>
    <div className="flex min-w-0 items-center gap-3">
      <div className="flex size-11 shrink-0 items-center justify-center">
        <UserButton appearance={{ elements: { avatarBox: "size-11" } }} />
      </div>
      <p className="min-w-0 text-ink-dim">
        <span className="block">Signed in as</span>
        <span className="block text-ink [overflow-wrap:anywhere]">{user?.primaryEmailAddress?.emailAddress}</span>
      </p>
    </div>
    <p className="text-ink-dim">Use your profile menu to manage your email, password, and signed-in devices.</p>
    <SignOutButton redirectUrl="/login">
      <button type="button" className="min-h-11 w-full border border-ink/25 px-4 py-2 text-ink transition-colors hover:border-ink/50 hover:bg-ink/5 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">Log out</button>
    </SignOutButton>
  </section>;
}
