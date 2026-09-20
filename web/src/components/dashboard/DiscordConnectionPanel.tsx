"use client";

import { useEffect, useRef, useState, type FormEvent } from "react";
import { Sheet } from "@/components/marketing/Sheet";
import { useDiscordConnection, type DiscordConnectionState } from "./useDiscordConnection";

const actionClass = "min-h-11 border border-ink/25 px-4 py-2 text-[13px] transition-colors hover:border-ink/50 hover:bg-ink/5 disabled:cursor-not-allowed disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";
const inputClass = "min-h-11 w-full min-w-0 border border-ink/30 bg-paper-white px-3 py-2 text-ink disabled:opacity-50 focus-visible:outline-2 focus-visible:outline-offset-4 focus-visible:outline-ink";

function Feedback({ result }: { result?: { status: "success" | "error"; message: string } }) {
  return result ? <p role={result.status === "error" ? "alert" : "status"} className={result.status === "error" ? "text-stamp" : "text-ink-dim"}>{result.message}</p> : null;
}

export function DiscordWebhookForm({ id, create = false, disabled, pending, onSave, onCancel }: {
  id: string;
  create?: boolean;
  disabled: boolean;
  pending: boolean;
  onSave: (label: string, url: string) => Promise<"saved" | "uncertain" | "failed" | "ignored">;
  onCancel?: () => void;
}) {
  const [label, setLabel] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState("");
  const scopeRef = useRef<AbortController | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    scopeRef.current = controller;
    return () => controller.abort();
  }, []);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (disabled) return;
    if (create && (!label.trim() || label.length > 120)) {
      setError("Enter a destination label between 1 and 120 characters.");
      return;
    }
    if (!url.trim() || url.length > 2048) {
      setError("Enter a Discord webhook URL between 1 and 2048 characters.");
      return;
    }
    setError("");
    const scope = scopeRef.current;
    const outcome = await onSave(label.trim(), url.trim());
    if (!scope || scope.signal.aborted) return;
    if (outcome === "saved" || outcome === "uncertain") {
      setUrl("");
      if (create && outcome === "saved") setLabel("");
    }
  }

  return <form onSubmit={(event) => void submit(event)} noValidate autoComplete="off" className="space-y-3">
    {create && <div className="space-y-1">
      <label htmlFor={`${id}-label`} className="block">Destination label</label>
      <input id={`${id}-label`} value={label} onChange={(event) => setLabel(event.target.value)} maxLength={120} required disabled={disabled} className={inputClass} placeholder="e.g. Collectibles" />
    </div>}
    <div className="space-y-1">
      <label htmlFor={`${id}-url`} className="block">{create ? "Discord webhook URL" : "Replacement webhook URL"}</label>
      <input id={`${id}-url`} type="password" value={url} onChange={(event) => setUrl(event.target.value)} maxLength={2048} required disabled={disabled} autoComplete="off" spellCheck={false} autoCapitalize="none" aria-describedby={`${id}-hint`} className={inputClass} />
      <p id={`${id}-hint`} className="text-[12px] text-ink-dim">Copy the webhook URL from your Discord channel’s integration settings. Saved URLs are kept private and cannot be displayed here.</p>
    </div>
    {error && <p role="alert" className="text-stamp">{error}</p>}
    <div className="flex flex-wrap gap-3">
      <button type="submit" disabled={disabled} className={actionClass}>{pending ? "Saving…" : create ? "Save destination" : "Save replacement"}</button>
      {onCancel && <button type="button" onClick={onCancel} disabled={disabled} className={actionClass}>Cancel</button>}
    </div>
  </form>;
}

export function DiscordConnectionPanel({ state }: { state: DiscordConnectionState }) {
  const actions = useDiscordConnection(state);
  const [editingId, setEditingId] = useState<string | null>(null);
  const { destinations } = state;
  const disabled = state.destinationMutationPending || destinations.status !== "loaded";

  return <Sheet className="min-w-0 p-5 sm:p-7">
    <section aria-labelledby="destinations-heading" className="min-w-0 space-y-5">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-dashed border-ink/25 pb-4">
        <h2 id="destinations-heading" className="text-[18px] uppercase tracking-[0.06em]">Discord connections</h2>
        <button type="button" onClick={() => void state.retryDestinations()} disabled={state.destinationMutationPending || destinations.status === "loading"} aria-label={`${destinations.status === "error" ? "Retry" : "Refresh"} destinations`} className={actionClass}>{destinations.status === "error" ? "Try again" : "Refresh"}</button>
      </div>
      <p className="text-ink-dim">Save a destination for your alerts, then send a test message to check it. Saving a URL does not send a message.</p>
      {destinations.status === "loading" && <p role="status">{destinations.data === null ? "Loading" : "Refreshing"} destinations…</p>}
      {destinations.status === "error" && <p role="alert" className="text-stamp">{destinations.error}{destinations.data !== null && " Showing the last saved data; it may be out of date."}</p>}
      <div className="space-y-3">
        <h3 className="text-[16px]">Add a destination</h3>
        <DiscordWebhookForm id="new-destination" create disabled={disabled} pending={actions.pending?.kind === "create"} onSave={(label, webhook_url) => actions.run({ kind: "create", input: { label, webhook_url } })} />
        <Feedback result={actions.createResult} />
      </div>
      {destinations.data?.length === 0 && <p className="text-ink-dim">No destinations saved yet.</p>}
      {!!destinations.data?.length && <ul className="divide-y divide-dashed divide-ink/25 border-t border-dashed border-ink/25">
        {destinations.data.map((destination) => <li key={destination.id} className="min-w-0 space-y-3 py-5 last:pb-0">
          <h3 className="text-[16px] [overflow-wrap:anywhere]">{destination.label}</h3>
          <p className="text-[12px] text-ink-dim [overflow-wrap:anywhere]">{destination.verified_at
            ? <>Previously verified: <time dateTime={destination.verified_at}>{destination.verified_at}</time>. This is historical verification, not a current connection check.</>
            : "This saved webhook has not been verified yet."}</p>
          <Feedback result={actions.results[destination.id]?.save} />
          <Feedback result={actions.results[destination.id]?.test} />
          <div className="flex flex-wrap gap-3">
            <button type="button" onClick={() => void actions.run({ kind: "test", id: destination.id })} disabled={disabled} aria-label={`Send test message to ${destination.label}`} className={actionClass}>{actions.pending?.kind === "test" && actions.pending.id === destination.id ? "Sending test…" : "Send test message"}</button>
            <button type="button" onClick={() => setEditingId(destination.id)} disabled={disabled} aria-expanded={editingId === destination.id} aria-controls={`replace-${destination.id}`} className={actionClass}>Replace webhook URL</button>
          </div>
          {editingId === destination.id && <div id={`replace-${destination.id}`} className="border-l-2 border-ink/25 pl-4">
            <DiscordWebhookForm id={`destination-${destination.id}`} disabled={disabled} pending={actions.pending?.kind === "replace" && actions.pending.id === destination.id} onCancel={() => setEditingId(null)} onSave={(_label, webhook_url) => actions.run({ kind: "replace", id: destination.id, webhook_url })} />
          </div>}
        </li>)}
      </ul>}
    </section>
  </Sheet>;
}
