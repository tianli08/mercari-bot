import { apiFetch } from "./api";

/** Public destination metadata never includes webhook credentials or ownership. */
export type PublicDestination = {
  id: string;
  type: "discord_webhook";
  label: string;
  verified_at: string | null;
  created_at: string;
  updated_at: string;
};

export type PublicWatchlistFilters = {
  min_price: number | null;
  max_price: number | null;
  /** Listing status, not Mercari item-condition grades. */
  condition: "active" | "sold" | "any";
};

export type PublicWatchlist = {
  id: string;
  name: string;
  keywords: string[];
  filters: PublicWatchlistFilters;
  destination_id: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
};

export type DashboardReadOptions = {
  signal?: AbortSignal;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function isDestination(value: unknown): value is PublicDestination {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    value.type === "discord_webhook" &&
    typeof value.label === "string" &&
    (value.verified_at === null || typeof value.verified_at === "string") &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

function isNullablePrice(value: unknown): value is number | null {
  return value === null || (typeof value === "number" && Number.isInteger(value));
}

function isWatchlist(value: unknown): value is PublicWatchlist {
  return (
    isRecord(value) &&
    typeof value.id === "string" &&
    typeof value.name === "string" &&
    Array.isArray(value.keywords) &&
    value.keywords.every((keyword) => typeof keyword === "string") &&
    isRecord(value.filters) &&
    isNullablePrice(value.filters.min_price) &&
    isNullablePrice(value.filters.max_price) &&
    ["active", "sold", "any"].includes(value.filters.condition as string) &&
    typeof value.destination_id === "string" &&
    typeof value.enabled === "boolean" &&
    typeof value.created_at === "string" &&
    typeof value.updated_at === "string"
  );
}

/** Callers obtain a current bearer token for each read; this module retains none. */
export async function listDestinations(
  token: string,
  options?: DashboardReadOptions,
): Promise<PublicDestination[]> {
  const response = await apiFetch<unknown>("/destinations", {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
    signal: options?.signal,
  });

  if (!Array.isArray(response) || !response.every(isDestination)) {
    throw new TypeError("Invalid destinations response");
  }
  return response;
}

/** Preserve normalized filters and keywords exactly as returned by the API. */
export async function listWatchlists(
  token: string,
  options?: DashboardReadOptions,
): Promise<PublicWatchlist[]> {
  const response = await apiFetch<unknown>("/watchlists", {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
    signal: options?.signal,
  });

  if (!Array.isArray(response) || !response.every(isWatchlist)) {
    throw new TypeError("Invalid watchlists response");
  }
  return response;
}
