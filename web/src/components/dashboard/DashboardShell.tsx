"use client";

import { useState, type ReactNode } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { SignOutButton, useAuth } from "@clerk/nextjs";
import { AccountHome } from "@/components/auth/AccountHome";
import { Sheet } from "@/components/marketing/Sheet";
import { useDashboardState, type ResourceState } from "./useDashboardState";

const hasApplicationApi = Boolean(process.env.NEXT_PUBLIC_API_BASE_URL?.trim());
const actionClass = "min-h-11 border border-ink/25 px-4 py-2 text-[13px] transition-colors hover:border-ink/50 hover:bg-ink/5 disabled:cursor-wait disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

function ResourceSection<T>({ id, title, resource, retry, empty, children }: {
  id: string;
  title: string;
  resource: ResourceState<T>;
  retry: () => Promise<void>;
  empty: string;
  children: ReactNode;
}) {
  return <Sheet className="min-w-0 p-5 sm:p-7">
    <section aria-labelledby={id} className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-dashed border-ink/25 pb-4">
        <h2 id={id} className="text-[18px] uppercase tracking-[0.06em]">{title}</h2>
        <button type="button" onClick={() => void retry()} disabled={resource.status === "loading"} aria-label={`${resource.status === "error" ? "Retry" : "Refresh"} ${title.toLowerCase()}`} className={actionClass}>
          {resource.status === "error" ? "Try again" : "Refresh"}
        </button>
      </div>
      {resource.status === "loading" && <p role="status" className="text-ink-dim">{resource.data === null ? "Loading" : "Refreshing"} {title.toLowerCase()}…</p>}
      {resource.status === "error" && <p role="alert" className="text-stamp">{resource.error}{resource.data !== null && " Showing the last saved data; it may be out of date."}</p>}
      {resource.data !== null && (resource.data.length === 0
        ? <p className="text-ink-dim">{empty}</p>
        : children)}
    </section>
  </Sheet>;
}

function ApplicationDashboard({ getToken, retryAccount, welcome }: {
  getToken: () => Promise<string | null>;
  retryAccount: () => void;
  welcome: boolean;
}) {
  const dashboard = useDashboardState(getToken);
  const { access, destinations, watchlists, selectedWatchlist } = dashboard;

  if (access.status === "loading") return <Sheet className="p-5 sm:p-7"><p role="status">Loading your account…</p></Sheet>;
  if (access.status !== "ready") {
    const sessionExpired = access.status === "denied" && access.reason === "session";
    return <Sheet className="p-5 sm:p-7">
      <section aria-labelledby="access-heading" className="space-y-4">
        <h2 id="access-heading" className="text-[18px]">{access.status === "unavailable" ? "Account service unavailable" : sessionExpired ? "Sign in again" : "Application access unavailable"}</h2>
        <p role="alert" className="text-stamp">{access.status === "unavailable"
          ? "We couldn’t reach your application account. Please try again. Your profile and logout are still available."
          : sessionExpired
            ? "Your session can no longer access the application. Sign in again to continue."
            : "This account cannot access the application. Check email verification in your profile, or sign in with your existing account."}</p>
        <div className="flex flex-wrap gap-3">
          <button type="button" onClick={retryAccount} className={actionClass}>Retry account access</button>
          {access.status === "denied" && <SignOutButton redirectUrl="/login">
            <button type="button" className={actionClass}>{sessionExpired ? "Sign in again" : "Use another account"}</button>
          </SignOutButton>}
        </div>
      </section>
    </Sheet>;
  }

  const selectedDestination = destinations.data?.find((record) => record.id === selectedWatchlist?.destination_id);
  return <div className="min-w-0 space-y-6">
    {welcome && <p role="status" className="text-ink-dim">Your account is ready.</p>}
    <ResourceSection id="destinations-heading" title="Destinations" resource={destinations} retry={dashboard.retryDestinations} empty="No destinations saved yet.">
      <ul className="divide-y divide-dashed divide-ink/20">
        {destinations.data?.map((destination) => <li key={destination.id} className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3 first:pt-0 last:pb-0">
          <span className="min-w-0 [overflow-wrap:anywhere]">{destination.label}</span>
          <span className="text-[12px] text-ink-dim">Discord</span>
        </li>)}
      </ul>
    </ResourceSection>
    <ResourceSection id="watchlists-heading" title="Watchlists" resource={watchlists} retry={dashboard.retryWatchlists} empty="No watchlists saved yet.">
      <div className="space-y-5">
        <div className="space-y-2">
          <label htmlFor="selected-watchlist" className="block text-ink-dim">Selected watchlist</label>
          <select id="selected-watchlist" value={dashboard.selectedWatchlistId ?? ""} onChange={(event) => dashboard.selectWatchlist(event.target.value)} className="min-h-11 w-full min-w-0 border border-ink/30 bg-paper-white px-3 py-2 text-ink focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">
            {watchlists.data?.map((watchlist) => <option key={watchlist.id} value={watchlist.id}>{watchlist.name}</option>)}
          </select>
        </div>
        {selectedWatchlist && <div className="space-y-4 border-l-2 border-ink/25 pl-4">
          <h3 className="text-[16px] [overflow-wrap:anywhere]">{selectedWatchlist.name}</h3>
          <dl className="space-y-3">
            <div><dt className="text-[12px] text-ink-dim">Saved keywords</dt><dd>{selectedWatchlist.keywords.length}</dd></div>
            <div><dt className="text-[12px] text-ink-dim">Destination</dt><dd className="[overflow-wrap:anywhere]">{selectedDestination?.label ?? (destinations.status === "loading" ? "Loading destination…" : destinations.status === "error" ? "Destination details unavailable" : "Saved destination is no longer available")}</dd></div>
          </dl>
        </div>}
      </div>
    </ResourceSection>
  </div>;
}

export function DashboardShell() {
  const { isLoaded, userId, sessionId, getToken } = useAuth();
  const welcome = useSearchParams().get("welcome") === "1";
  const [attempt, setAttempt] = useState(0);

  if (!isLoaded) return <p role="status">Loading your account…</p>;
  if (!userId) return <p>Your session has ended. <Link href="/login" className="underline underline-offset-4 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink">Sign in</Link> to continue.</p>;

  return <div className="grid min-w-0 items-start gap-6 text-[13px] leading-relaxed lg:grid-cols-[minmax(0,1fr)_300px]">
    {hasApplicationApi ? <ApplicationDashboard
      // A new identity or explicit access retry starts with no tenant records.
      key={JSON.stringify([userId, sessionId, attempt])}
      getToken={getToken}
      retryAccount={() => setAttempt((previous) => previous + 1)}
      welcome={welcome}
    /> : <Sheet className="p-5 sm:p-7">
      <div className="space-y-4">
        {welcome && <p role="status">You’re signed in.</p>}
        <h2 className="text-[18px]">Monitoring features unavailable</h2>
        <p className="text-ink-dim">The application API is not configured for this site. You can still manage your profile and log out.</p>
      </div>
    </Sheet>}
    <Sheet tint="grey" className="min-w-0 p-5 sm:p-7"><AccountHome /></Sheet>
  </div>;
}
