"use client";

import { useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { createDestination, updateDestination, verifyDestination, type CreateDestinationInput } from "@/lib/dashboard-api";
import type { useDashboardState } from "./useDashboardState";

export type DiscordConnectionState = Pick<ReturnType<typeof useDashboardState>,
  "destinations" | "destinationMutationPending" | "getCurrentToken" | "reportAccessFailure" |
  "replaceDestination" | "beginDestinationMutation" | "reconcileDestinations" | "retryDestinations"
> & { accessSignal: AbortSignal };

type Result = { status: "success" | "error"; message: string };
type DestinationResult = { save?: Result; test?: Result };
type Operation =
  | { kind: "create"; input: CreateDestinationInput }
  | { kind: "replace"; id: string; webhook_url: string }
  | { kind: "test"; id: string };
type Outcome = "saved" | "uncertain" | "failed" | "ignored";

function testError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "webhook_rejected") return "Discord rejected this webhook. Replace the URL, then send a new test message.";
    if (error.code === "webhook_verification_failed") return "The server could not verify this webhook. Check the webhook in Discord, then replace it or try a test later.";
    if (error.code === "webhook_unavailable") return "Discord could not confirm delivery. Check the channel before sending another test later; a message may have arrived.";
    if (error.status === 404) return "This destination is no longer available. Refresh your destinations.";
    if (error.status === 429) return "Too many requests. Wait before sending another test.";
    if (error.status === 503 && error.code !== "unknown") return "The application service is temporarily unavailable. Try the test again later.";
  }
  return "The test result could not be confirmed. Check the Discord channel before sending another test; a message may have arrived.";
}

function saveError(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.code === "destination_label_exists") return "A destination already uses this label. Choose another label, or replace the existing destination’s webhook.";
    if (error.code === "invalid_webhook_url") return "Enter a valid Discord webhook URL copied from your channel’s integration settings.";
    if (error.status === 422) return "Check the label (up to 120 characters) and webhook URL (up to 2048 characters), then save again.";
    if (error.status === 404) return "This destination is no longer available. Refresh your destinations.";
    if (error.status === 429) return "Too many requests. Wait before saving again.";
  }
  return "The connection could not be saved. Please try again.";
}

/** Only metadata and safe, fixed copy survive each operation. No errors or URLs are retained here. */
export function useDiscordConnection(state: DiscordConnectionState) {
  const [createResult, setCreateResult] = useState<Result>();
  const [results, setResults] = useState<Record<string, DestinationResult>>({});
  const [pending, setPending] = useState<{ kind: Operation["kind"]; id?: string } | null>(null);
  const scopeRef = useRef<AbortController | null>(null);

  useEffect(() => {
    const controller = new AbortController();
    scopeRef.current = controller;
    const abort = () => controller.abort();
    if (state.accessSignal.aborted) abort();
    else state.accessSignal.addEventListener("abort", abort, { once: true });
    return () => {
      controller.abort();
      state.accessSignal.removeEventListener("abort", abort);
    };
  }, [state.accessSignal]);

  async function run(operation: Operation): Promise<Outcome> {
    const controller = scopeRef.current;
    if (!controller || controller.signal.aborted || state.destinations.status !== "loaded") return "ignored";
    const finish = state.beginDestinationMutation();
    if (!finish) return "ignored";
    const current = () => !controller.signal.aborted && scopeRef.current === controller;
    const { kind } = operation;
    setPending({ kind, ...(kind !== "create" ? { id: operation.id } : {}) });
    function result(value: Result, resetTest = false) {
      if (kind === "create") setCreateResult(value);
      else setResults((previous) => ({
        ...previous,
        [operation.id]: {
          ...previous[operation.id],
          ...(resetTest ? { test: undefined } : {}),
          [kind === "test" ? "test" : "save"]: value,
        },
      }));
    }
    let submitted = false;
    try {
      const token = await state.getCurrentToken();
      if (!current()) return "ignored";
      submitted = true;
      const options = { signal: controller.signal };
      const saved = kind === "create"
        ? await createDestination(token, operation.input, options)
        : kind === "replace"
          ? await updateDestination(token, operation.id, { webhook_url: operation.webhook_url }, options)
          : await verifyDestination(token, operation.id, options);
      if (!current()) return "ignored";
      state.replaceDestination(saved);
      result({ status: "success", message: kind === "create"
        ? "Destination saved. Send a test message when you’re ready."
        : kind === "replace"
          ? "Webhook replaced. Send a new test message to verify it."
          : "Test message sent. Check your Discord channel." }, kind === "replace");
      return "saved";
    } catch (error) {
      if (!current() || state.reportAccessFailure(error)) return "ignored";
      if (kind !== "test" && submitted && (!(error instanceof ApiError) || error.status >= 500 || error.status === 408)) {
        result({ status: "error", message: "The save result could not be confirmed. Refreshing saved destination metadata…" }, kind === "replace");
        // Keep the mutation gate held until this read finishes. A failed read
        // leaves writes disabled until a successful, explicit collection refresh.
        const refreshed = await state.reconcileDestinations();
        if (!current()) return "ignored";
        result({ status: "error", message: kind === "create"
          ? `The save result could not be confirmed. ${refreshed ? "Saved destinations have been refreshed. Check the labels below before saving again; use the existing destination if it was created." : "Refresh destinations successfully and check for the saved label before saving again."}`
          : `The replacement result could not be confirmed. ${refreshed ? "Saved metadata has been refreshed, but it cannot reveal which URL is stored. Check your Discord channel with an explicit test, or replace the URL again." : "Refresh destinations successfully before testing or replacing again. Saved metadata cannot reveal the stored URL."}` }, kind === "replace");
        return "uncertain";
      }
      result({ status: "error", message: !submitted
        ? "We couldn’t access your session. Please try again."
        : kind === "test" ? testError(error) : saveError(error) });
      return "failed";
    } finally {
      finish();
      if (current()) setPending(null);
    }
  }

  return { createResult, results, pending, run };
}
