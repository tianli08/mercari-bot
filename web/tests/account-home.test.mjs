import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { fixtures, loadSource } from "./helpers/dashboard-harness.mjs";

function dashboardFixture({ apiBase, access = { status: "ready" }, auth = {}, resources = {} } = {}) {
  const calls = { dashboard: 0, token: 0, signOutRedirects: [] };
  const clerk = {
    useAuth: () => ({ isLoaded: true, userId: "user-a", sessionId: "session-a", getToken: async () => { calls.token++; return "token"; }, ...auth }),
    useUser: () => ({ user: { primaryEmailAddress: { emailAddress: "person@example.com" } } }),
    UserButton: () => React.createElement("button", null, "Profile"),
    SignOutButton: ({ children, redirectUrl }) => { calls.signOutRedirects.push(redirectUrl); return children; },
  };
  const account = loadSource("src/components/auth/AccountHome.tsx", { "@clerk/nextjs": clerk });
  const sheet = loadSource("src/components/marketing/Sheet.tsx");
  const connection = loadSource("src/components/dashboard/useDiscordConnection.ts", {
    "@/lib/api": {}, "@/lib/dashboard-api": {},
  });
  const panel = loadSource("src/components/dashboard/DiscordConnectionPanel.tsx", {
    "@/components/marketing/Sheet": sheet, "./useDiscordConnection": connection,
  });
  const state = {
    access,
    destinations: { status: "loaded", data: fixtures.destinations, error: null },
    watchlists: { status: "loaded", data: fixtures.watchlists, error: null },
    selectedWatchlistId: fixtures.watchlists[0].id,
    selectedWatchlist: fixtures.watchlists[0],
    retryDestinations: async () => {}, retryWatchlists: async () => {}, selectWatchlist: () => {},
    ...resources,
  };
  const modules = {
    "@clerk/nextjs": clerk,
    "next/navigation": { useSearchParams: () => new URLSearchParams("welcome=1") },
    "next/link": { default: ({ children, ...props }) => React.createElement("a", props, children) },
    "@/components/auth/AccountHome": account,
    "@/components/marketing/Sheet": sheet,
    "./useDashboardState": { useDashboardState: () => { calls.dashboard++; return state; } },
    "./DiscordConnectionPanel": panel,
  };
  const { DashboardShell } = loadSource("src/components/dashboard/DashboardShell.tsx", modules, { NEXT_PUBLIC_API_BASE_URL: apiBase });
  return { html: renderToStaticMarkup(React.createElement(DashboardShell)), calls, modules };
}

test("frontend-only dashboard retains profile, logout and welcome without tokens or resource requests", () => {
  for (const apiBase of [undefined, "", "   "]) {
    const { html, calls } = dashboardFixture({ apiBase });
    assert.match(html, /person@example.com/);
    assert.match(html, /You’re signed in/);
    assert.match(html, /Use your profile menu/);
    assert.match(html, /Monitoring features unavailable/);
    assert.match(html, /Log out/);
    assert.doesNotMatch(html, /Loading your account|No watchlists|Saved keywords|Your account is ready/);
    assert.equal(calls.dashboard, 0);
    assert.equal(calls.token, 0);
    assert.deepEqual(calls.signOutRedirects, ["/login"]);
  }
});

test("Clerk readiness and signed-out state prevent mounting protected data loading", () => {
  for (const auth of [{ isLoaded: false }, { userId: null, sessionId: null }]) {
    const { html, calls } = dashboardFixture({ apiBase: "https://api.example.com", auth });
    assert.equal(calls.dashboard, 0);
    assert.doesNotMatch(html, /Saved keywords|person@example.com/);
    if (auth.isLoaded === false) assert.match(html, /Loading your account/);
    else assert.match(html, /href="\/login"/);
  }
});

test("configured dashboard has one account-state owner and labeled saved-resource selection", () => {
  const { html, calls } = dashboardFixture({ apiBase: "https://api.example.com" });
  assert.equal(calls.dashboard, 1);
  assert.match(html, /Your account is ready/);
  assert.match(html, /Collectibles/);
  assert.match(html, /for="selected-watchlist"/);
  assert.match(html, /value="watchlist_active" selected/);
  assert.match(html, /Saved keywords/);
  assert.match(html, /Profile/);
  assert.match(html, /Log out/);
});

test("resource failure is announced with retry and stale data while the other list stays visible", () => {
  const { html } = dashboardFixture({ apiBase: "https://api.example.com", resources: {
    destinations: { status: "error", data: fixtures.destinations, error: "Destinations unavailable." },
  } });
  assert.match(html, /role="alert"/);
  assert.match(html, /Retry destinations/);
  assert.match(html, /may be out of date/);
  assert.match(html, /Collectibles/);
  assert.match(html, /Selected watchlist/);
});

test("loaded empty collections have truthful empty states", () => {
  const { html } = dashboardFixture({ apiBase: "https://api.example.com", resources: {
    destinations: { status: "loaded", data: [], error: null },
    watchlists: { status: "loaded", data: [], error: null },
    selectedWatchlist: null,
  } });
  assert.match(html, /No destinations saved yet/);
  assert.match(html, /No watchlists saved yet/);
  assert.doesNotMatch(html, /role="alert"|<select|Saved keywords/);
});

test("loading, unavailable, session loss and account conflict retain account controls and distinct recovery", () => {
  for (const [access, expected] of [
    [{ status: "loading" }, /Loading your account/],
    [{ status: "unavailable" }, /Account service unavailable/],
    [{ status: "denied", reason: "session" }, /Sign in again/],
    [{ status: "denied", reason: "account" }, /Use another account/],
  ]) {
    const { html, calls } = dashboardFixture({ apiBase: "https://api.example.com", access });
    assert.match(html, expected);
    assert.match(html, /Profile/);
    assert.match(html, /Log out/);
    assert.doesNotMatch(html, /Collectibles|Selected watchlist|No watchlists/);
    if (access.status !== "loading") assert.match(html, /Retry account access/);
    assert.ok(calls.signOutRedirects.every((url) => url === "/login"));
  }
});

test("the application subtree is keyed by both Clerk account and session", () => {
  const keys = [];
  for (const [userId, sessionId] of [["a", "1"], ["b", "1"], ["b", "2"]]) {
    const { modules } = dashboardFixture({ auth: { userId, sessionId } });
    const { DashboardShell } = loadSource("src/components/dashboard/DashboardShell.tsx", {
      ...modules, react: { ...React, useState: () => [0, () => {}] },
    }, { NEXT_PUBLIC_API_BASE_URL: "https://api.example.com" });
    const tree = DashboardShell();
    keys.push(tree.props.children[0].key);
  }
  assert.equal(new Set(keys).size, 3);
});
