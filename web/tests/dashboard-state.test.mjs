import assert from "node:assert/strict";
import test from "node:test";
import { ApiError, deferred, fixtures, flush, mountDashboard } from "./helpers/dashboard-harness.mjs";

const { destinations, watchlists } = fixtures;
const failure = (status, code = "unavailable") => new ApiError(status, code, "Controlled failure");

test("account access precedes concurrent resource reads, each with a fresh token", async () => {
  const account = deferred(), destination = deferred(), watchlist = deferred();
  const app = mountDashboard({ account: () => account.promise, destinations: () => destination.promise, watchlists: () => watchlist.promise });
  await flush();
  assert.deepEqual(app.calls.map(({ name }) => name), ["account"]);
  assert.equal(app.value.access.status, "loading");
  account.resolve({ id: "account-a" });
  await flush();
  assert.deepEqual(app.calls.map(({ name, token }) => [name, token]), [["account", "token-1"], ["destinations", "token-2"], ["watchlists", "token-3"]]);
  destination.resolve(destinations);
  await flush();
  assert.equal(app.value.destinations.status, "loaded");
  assert.equal(app.value.watchlists.status, "loading");
  watchlist.resolve([]);
  await flush();
  assert.equal(app.value.watchlists.status, "loaded");
  assert.equal(app.value.watchlists.data.length, 0);
  assert.equal(app.value.selectedWatchlistId, null);
  app.unmount();
});

for (const resource of ["destinations", "watchlists"]) {
  test(`${resource} failure is independent and a successful retry uses a new token`, async () => {
    let fail = true;
    const app = mountDashboard({ [resource]: async () => { if (fail) throw failure(503); return fixtures[resource]; } });
    await flush();
    assert.equal(app.value[resource].status, "error");
    assert.equal(app.value[resource].data, null);
    assert.equal(app.value[resource === "destinations" ? "watchlists" : "destinations"].status, "loaded");
    fail = false;
    await app.value[resource === "destinations" ? "retryDestinations" : "retryWatchlists"]();
    await flush();
    assert.equal(app.value[resource].status, "loaded");
    assert.equal(app.calls.at(-1).token, "token-4");
    assert.equal(app.calls.filter(({ name }) => name === "account").length, 1);
    app.unmount();
  });
}

for (const [error, status, reason] of [
  [failure(401), "denied", "session"],
  [failure(403), "denied", "account"],
  [failure(409, "account_conflict"), "denied", "account"],
  [failure(503), "unavailable", undefined],
  [new TypeError("offline"), "unavailable", undefined],
]) {
  test(`account ${error.status ?? "network"} failure does not load resources`, async () => {
    const app = mountDashboard({ account: async () => { throw error; } });
    await flush();
    assert.equal(app.value.access.status, status);
    assert.equal(app.value.access.reason, reason);
    assert.equal(app.calls.length, 1);
    assert.equal(app.value.destinations.data, null);
    assert.equal(app.value.watchlists.data, null);
    app.unmount();
  });
}

for (const status of [401, 403]) {
  test(`resource ${status} clears tenant data, aborts pending reads, and blocks later protected calls`, async () => {
    const pending = deferred();
    const app = mountDashboard({ destinations: () => pending.promise });
    await flush();
    const oldActions = app.value;
    const signal = oldActions.accessSignal;
    assert.equal(oldActions.watchlists.status, "loaded");
    assert.equal(oldActions.reportAccessFailure(failure(status)), true);
    await flush();
    assert.equal(app.value.access.status, "denied");
    assert.equal(app.value.watchlists.data, null);
    assert.equal(app.value.selectedWatchlistId, null);
    assert.equal(signal.aborted, true);
    assert.ok(app.calls.every(({ signal }) => signal.aborted));
    pending.resolve(destinations);
    oldActions.replaceWatchlist(watchlists[0]);
    oldActions.replaceDestination(destinations[0]);
    oldActions.selectWatchlist(watchlists[0].id);
    await oldActions.retryWatchlists();
    await assert.rejects(oldActions.getCurrentToken(), { name: "AbortError" });
    await flush();
    assert.equal(app.value.destinations.data, null);
    assert.equal(app.value.watchlists.data, null);
    assert.equal(app.calls.length, 3);
    app.unmount();
  });
}

test("a read reporting denied access uses the shared failure handler", async () => {
  const app = mountDashboard({ watchlists: async () => { throw failure(403); } });
  await flush();
  assert.equal(app.value.access.status, "denied");
  assert.equal(app.value.destinations.data, null);
  app.unmount();
});

test("a missing or expired token is a session failure, never a resource empty state", async () => {
  let token = null;
  const app = mountDashboard({ getToken: async () => token });
  await flush();
  assert.equal(app.value.access.reason, "session");
  assert.equal(app.calls.length, 0);
  app.unmount();
  token = "valid";
  const next = mountDashboard({ getToken: async () => token });
  await flush();
  token = null;
  await next.value.retryDestinations();
  await flush();
  assert.equal(next.value.access.reason, "session");
  assert.equal(next.value.watchlists.data, null);
  next.unmount();
});

test("selection survives reordering and refresh failure, then replaces or clears removed IDs", async () => {
  let records = [...watchlists].reverse();
  let fail = false;
  const app = mountDashboard({ watchlists: async () => { if (fail) throw new TypeError("offline"); return records; } });
  await flush();
  assert.equal(app.value.selectedWatchlistId, "watchlist_active");
  app.value.selectWatchlist("watchlist_sold");
  await flush();
  records = [...watchlists];
  await app.value.retryWatchlists();
  await flush();
  assert.equal(app.value.selectedWatchlistId, "watchlist_sold");
  fail = true;
  await app.value.retryWatchlists();
  await flush();
  assert.equal(app.value.watchlists.status, "error");
  assert.equal(app.value.watchlists.data.length, 3);
  assert.equal(app.value.selectedWatchlistId, "watchlist_sold");
  fail = false;
  records = watchlists.filter(({ id }) => id !== "watchlist_sold");
  await app.value.retryWatchlists();
  await flush();
  assert.equal(app.value.selectedWatchlistId, "watchlist_active");
  app.value.selectWatchlist("foreign-id");
  await flush();
  assert.equal(app.value.selectedWatchlistId, "watchlist_active");
  records = [];
  await app.value.retryWatchlists();
  await flush();
  assert.equal(app.value.selectedWatchlistId, null);
  app.unmount();
});

test("newer retries and saved records cannot be overwritten by older collection reads", async () => {
  const delayed = deferred();
  let slow = false;
  const app = mountDashboard({ watchlists: async () => slow ? delayed.promise : watchlists });
  await flush();
  slow = true;
  const oldRead = app.value.retryWatchlists();
  await flush();
  const oldSignal = app.calls.at(-1).signal;
  slow = false;
  await app.value.retryWatchlists();
  await flush();
  assert.equal(oldSignal.aborted, true);
  const saved = { ...watchlists[0], name: "Saved name", keywords: ["saved"] };
  app.value.replaceWatchlist(saved);
  app.value.replaceDestination({ ...destinations[0], label: "Saved destination" });
  delayed.resolve([]);
  await oldRead;
  await flush();
  assert.equal(app.value.selectedWatchlist.name, "Saved name");
  assert.equal(app.value.selectedWatchlist.filters, watchlists[0].filters);
  assert.equal(app.value.destinations.data[0].label, "Saved destination");
  assert.equal(app.value.watchlists.data.length, 3);
  app.unmount();
});

for (const stage of ["token", "account", "destinations"]) {
  test(`account switch/unmount during delayed ${stage} discards old responses and callbacks`, async () => {
    const delayed = deferred();
    const app = mountDashboard(stage === "token" ? { getToken: () => delayed.promise } : { [stage]: () => delayed.promise });
    await flush();
    const oldActions = app.value;
    app.unmount();
    const next = mountDashboard({ destinations: async () => [], watchlists: async () => [] });
    assert.equal(next.value.access.status, "loading");
    assert.equal(next.value.destinations.data, null);
    delayed.resolve(stage === "token" ? "old-token" : stage === "account" ? { id: "old-account" } : destinations);
    oldActions.replaceWatchlist(watchlists[0]);
    oldActions.replaceDestination(destinations[0]);
    oldActions.reportAccessFailure(failure(403));
    await flush();
    assert.equal(app.settersAfterUnmount, 0);
    assert.equal(next.value.watchlists.data.length, 0);
    assert.equal(next.value.destinations.data.length, 0);
    assert.equal(next.value.selectedWatchlistId, null);
    assert.equal(next.value.access.status, "ready");
    assert.ok(app.calls.every(({ signal }) => signal.aborted));
    next.unmount();
  });
}

test("effect replay discards the first account check and retains one active resource lifecycle", async () => {
  const app = mountDashboard();
  app.replayEffects();
  await flush();
  assert.equal(app.value.access.status, "ready");
  assert.deepEqual(app.calls.map(({ name }) => name), ["account", "destinations", "watchlists"]);
  app.unmount();
});

test("saved records abort older reads without hiding an incomplete or failed collection", async () => {
  const pending = deferred();
  const app = mountDashboard({ watchlists: () => pending.promise, destinations: async () => { throw failure(503); } });
  await flush();
  const watchSignal = app.calls.find(({ name }) => name === "watchlists").signal;
  app.value.replaceWatchlist(watchlists[0]);
  app.value.replaceDestination(destinations[0]);
  pending.resolve([]);
  await flush();
  assert.equal(watchSignal.aborted, true);
  assert.equal(app.value.selectedWatchlistId, watchlists[0].id);
  assert.equal(app.value.watchlists.status, "error");
  assert.equal(app.value.watchlists.data.length, 1);
  assert.match(app.value.watchlists.error, /complete list/);
  assert.equal(app.value.destinations.status, "error");
  assert.equal(app.value.destinations.data.length, 1);
  app.unmount();
});
