import type { PublicDestination, PublicWatchlist } from "../../src/lib/dashboard-api";

// Representative public API responses, also checked by the production TypeScript build.
export const destinations = [
  {
    id: "destination_unverified",
    type: "discord_webhook",
    label: "Collectibles",
    verified_at: null,
    created_at: "2026-09-18T10:00:00Z",
    updated_at: "2026-09-18T10:00:00Z",
  },
  {
    id: "destination_verified",
    type: "discord_webhook",
    label: "Games",
    verified_at: "2026-09-19T12:30:00.123456Z",
    created_at: "2026-09-18T11:00:00Z",
    updated_at: "2026-09-19T12:30:00.123456Z",
  },
] satisfies PublicDestination[];

export const watchlists = [
  {
    id: "watchlist_active",
    name: "Active listings",
    keywords: ["pokemon cards", "ポケモン"],
    filters: { min_price: 0, max_price: 2500, condition: "active" },
    destination_id: "destination_verified",
    enabled: true,
    created_at: "2026-09-18T10:00:00Z",
    updated_at: "2026-09-19T12:30:00.123456Z",
  },
  {
    id: "watchlist_sold",
    name: "Sold listings",
    keywords: ["retro games"],
    filters: { min_price: 500, max_price: null, condition: "sold" },
    destination_id: "destination_verified",
    enabled: false,
    created_at: "2026-09-18T10:00:00Z",
    updated_at: "2026-09-18T10:00:00Z",
  },
  {
    id: "watchlist_empty",
    name: "New watchlist",
    keywords: [],
    filters: { min_price: null, max_price: null, condition: "any" },
    destination_id: "destination_unverified",
    enabled: false,
    created_at: "2026-09-19T10:00:00Z",
    updated_at: "2026-09-19T10:00:00Z",
  },
] satisfies PublicWatchlist[];
