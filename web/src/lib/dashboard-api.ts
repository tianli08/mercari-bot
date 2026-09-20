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

export type CreateDestinationInput = { label: string; webhook_url: string };
export type UpdateDestinationInput =
  | { label: string; webhook_url?: string }
  | { label?: string; webhook_url: string };

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

// Keep only public metadata even if a server accidentally adds private fields.
function publicDestination(value: PublicDestination): PublicDestination {
  const { id, type, label, verified_at, created_at, updated_at } = value;
  return { id, type, label, verified_at, created_at, updated_at };
}

async function writeDestination(
  token: string,
  path: string,
  method: "POST" | "PATCH",
  input: CreateDestinationInput | UpdateDestinationInput | undefined,
  options?: DashboardReadOptions,
): Promise<PublicDestination> {
  const response = await apiFetch<unknown>(path, {
    method,
    cache: "no-store",
    headers: {
      Authorization: `Bearer ${token}`,
      ...(input ? { "Content-Type": "application/json" } : {}),
    },
    body: input ? JSON.stringify(input) : undefined,
    signal: options?.signal,
  });
  if (!isDestination(response)) throw new TypeError("Invalid destination response");
  return publicDestination(response);
}

/** Writes are never retried here, including explicit test-message requests. */
export function createDestination(token: string, input: CreateDestinationInput, options?: DashboardReadOptions) {
  return writeDestination(token, "/destinations", "POST", { label: input.label, webhook_url: input.webhook_url }, options);
}

export function updateDestination(token: string, id: string, input: UpdateDestinationInput, options?: DashboardReadOptions) {
  return writeDestination(token, `/destinations/${encodeURIComponent(id)}`, "PATCH", {
    ...(input.label !== undefined ? { label: input.label } : {}),
    ...(input.webhook_url !== undefined ? { webhook_url: input.webhook_url } : {}),
  } as UpdateDestinationInput, options);
}

export function verifyDestination(token: string, id: string, options?: DashboardReadOptions) {
  return writeDestination(token, `/destinations/${encodeURIComponent(id)}/verify`, "POST", undefined, options);
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
  return response.map(publicDestination);
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
