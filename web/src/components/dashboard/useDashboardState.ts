"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { ApiError } from "@/lib/api";
import { getCurrentUser, type PublicUser } from "@/lib/auth-api";
import { listDestinations, listWatchlists, type PublicDestination, type PublicWatchlist } from "@/lib/dashboard-api";

export type ResourceState<T> = {
  status: "loading" | "loaded" | "error";
  // null means not yet loaded; [] means a confirmed empty collection.
  data: T[] | null;
  error: string | null;
};

type AccessState =
  | { status: "loading" }
  | { status: "ready"; account: PublicUser; signal: AbortSignal }
  | { status: "denied"; reason: "session" | "account" }
  | { status: "unavailable" };

type DashboardState = {
  access: AccessState;
  destinations: ResourceState<PublicDestination>;
  watchlists: ResourceState<PublicWatchlist>;
  selectedWatchlistId: string | null;
};

function initialState(): DashboardState {
  return {
    access: { status: "loading" },
    destinations: { status: "loading", data: null, error: null },
    watchlists: { status: "loading", data: null, error: null },
    selectedWatchlistId: null,
  };
}

function accessFailure(error: unknown): "session" | "account" | null {
  if (!(error instanceof ApiError)) return null;
  if (error.status === 401) return "session";
  if (error.status === 403 || error.code === "account_conflict") return "account";
  return null;
}

function selectExisting(records: PublicWatchlist[], selected: string | null) {
  if (records.some((record) => record.id === selected)) return selected;
  // IDs give a stable first choice even when the API changes collection order.
  return records.map((record) => record.id).sort()[0] ?? null;
}

function replaceRecord<T extends { id: string }>(records: T[] | null, saved: T): T[] {
  return records?.some((record) => record.id === saved.id)
    ? records.map((record) => record.id === saved.id ? saved : record)
    : [...(records ?? []), saved];
}

function adoptSavedRecord<T extends { id: string }>(resource: ResourceState<T>, saved: T): ResourceState<T> & { data: T[] } {
  const data = replaceRecord(resource.data, saved);
  if (resource.status === "error") return { ...resource, data };
  if (resource.data === null) {
    return { status: "error", data, error: "Your change is saved. Refresh to load the complete list." };
  }
  return { status: "loaded", data, error: null };
}

/** Mount once per Clerk user/session and retry attempt (see DashboardShell). */
export function useDashboardState(getToken: () => Promise<string | null>) {
  const [state, setState] = useState<DashboardState>(initialState);
  const scopeRef = useRef<{
    active: boolean;
    authorized: boolean;
    getToken: typeof getToken;
    controller: AbortController;
    destinations: AbortController | null;
    watchlists: AbortController | null;
  } | null>(null);
  const getScope = useCallback(() => {
    const scope = scopeRef.current;
    return scope?.active && scope.getToken === getToken ? scope : null;
  }, [getToken]);

  const reportAccessFailure = useCallback((error: unknown) => {
    const reason = accessFailure(error);
    const scope = getScope();
    if (!reason || !scope || scope.controller.signal.aborted) return false;
    scope.authorized = false;
    scope.controller.abort();
    scope.destinations?.abort();
    scope.watchlists?.abort();
    setState({ ...initialState(), access: { status: "denied", reason } });
    return true;
  }, [getScope]);

  const currentToken = useCallback(async (signal: AbortSignal) => {
    if (signal.aborted) throw new DOMException("Obsolete request", "AbortError");
    const token = await getToken();
    if (signal.aborted) throw new DOMException("Obsolete request", "AbortError");
    if (!token) throw new ApiError(401, "authentication_required", "Session unavailable");
    return token;
  }, [getToken]);

  const getCurrentToken = useCallback(async () => {
    const scope = getScope();
    if (!scope?.authorized) throw new DOMException("Application access required", "AbortError");
    const signal = scope.controller.signal;
    try {
      return await currentToken(signal);
    } catch (error) {
      if (!signal.aborted) reportAccessFailure(error);
      throw error;
    }
  }, [currentToken, reportAccessFailure, getScope]);

  const readResource = useCallback(async (resource: "destinations" | "watchlists") => {
    const scope = getScope();
    if (!scope?.authorized) return;
    scope[resource]?.abort();
    const controller = new AbortController();
    scope[resource] = controller;
    const isCurrent = () => scope.active && scope.authorized && !controller.signal.aborted;
    setState((previous) => ({
      ...previous,
      [resource]: { ...previous[resource], status: "loading", error: null },
    }));
    try {
      const token = await getCurrentToken();
      if (!isCurrent()) return;
      if (resource === "destinations") {
        const data = await listDestinations(token, { signal: controller.signal });
        if (isCurrent()) setState((previous) => ({ ...previous, destinations: { status: "loaded", data, error: null } }));
      } else {
        const data = await listWatchlists(token, { signal: controller.signal });
        if (isCurrent()) setState((previous) => ({
          ...previous,
          watchlists: { status: "loaded", data, error: null },
          selectedWatchlistId: selectExisting(data, previous.selectedWatchlistId),
        }));
      }
    } catch (error) {
      if (!isCurrent() || reportAccessFailure(error)) return;
      setState((previous) => ({
        ...previous,
        [resource]: {
          ...previous[resource],
          status: "error",
          error: `We couldn’t load your ${resource}. Please try again.`,
        },
      }));
    }
  }, [getCurrentToken, reportAccessFailure, getScope]);

  useEffect(() => {
    // Each setup gets its own scope, including React Strict Mode's replay.
    const scope = {
      active: true,
      authorized: false,
      getToken,
      controller: new AbortController(),
      destinations: null as AbortController | null,
      watchlists: null as AbortController | null,
    };
    scopeRef.current = scope;
    const signal = scope.controller.signal;
    async function loadAccount() {
      try {
        const token = await currentToken(signal);
        if (signal.aborted) return;
        const account = await getCurrentUser(token, { signal });
        if (signal.aborted) return;
        scope.authorized = true;
        setState({ ...initialState(), access: { status: "ready", account, signal } });
        // Neither resource waits for the other to finish.
        void readResource("destinations");
        void readResource("watchlists");
      } catch (error) {
        if (!scope.active || signal.aborted || reportAccessFailure(error)) return;
        setState({ ...initialState(), access: { status: "unavailable" } });
      }
    }
    void loadAccount();
    return () => {
      scope.active = false;
      scope.authorized = false;
      scope.controller.abort();
      scope.destinations?.abort();
      scope.watchlists?.abort();
    };
  }, [currentToken, getToken, readResource, reportAccessFailure]);

  const replaceDestination = useCallback((saved: PublicDestination) => {
    const scope = getScope();
    if (!scope?.authorized) return;
    // A collection read begun before a save must not overwrite that save.
    scope.destinations?.abort();
    setState((previous) => ({
      ...previous,
      destinations: adoptSavedRecord(previous.destinations, saved),
    }));
  }, [getScope]);

  const replaceWatchlist = useCallback((saved: PublicWatchlist) => {
    const scope = getScope();
    if (!scope?.authorized) return;
    scope.watchlists?.abort();
    setState((previous) => {
      const watchlists = adoptSavedRecord(previous.watchlists, saved);
      return {
        ...previous,
        watchlists,
        selectedWatchlistId: selectExisting(watchlists.data, previous.selectedWatchlistId),
      };
    });
  }, [getScope]);

  const selectWatchlist = useCallback((id: string) => {
    const scope = getScope();
    if (!scope?.authorized) return;
    setState((previous) => previous.watchlists.data?.some((record) => record.id === id)
      ? { ...previous, selectedWatchlistId: id }
      : previous);
  }, [getScope]);

  const retryDestinations = useCallback(() => readResource("destinations"), [readResource]);
  const retryWatchlists = useCallback(() => readResource("watchlists"), [readResource]);

  return {
    ...state,
    selectedWatchlist: state.watchlists.data?.find((record) => record.id === state.selectedWatchlistId) ?? null,
    selectWatchlist,
    retryDestinations,
    retryWatchlists,
    replaceDestination,
    replaceWatchlist,
    getCurrentToken,
    reportAccessFailure,
    // Future protected polling/mutations must also stop on this signal.
    accessSignal: state.access.status === "ready" ? state.access.signal : undefined,
  };
}
