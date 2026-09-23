import assert from "node:assert/strict";
import test from "node:test";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { ApiError, deferred, fixtures, flush, loadSource, mountDashboard, mountHook } from "./helpers/dashboard-harness.mjs";

const secret = "https://discord.com/api/webhooks/123/temporary-test-secret";
const created = { ...fixtures.destinations[0], id: "new-id", label: "New channel" };
const failure = (status, code) => new ApiError(status, code, `Never show this: ${secret}`);

async function setup(overrides = {}, ownerOverrides = {}) {
  const owner = mountDashboard(ownerOverrides);
  await flush();
  const calls = [];
  const hook = mountHook((hooks) => {
    const api = {};
    for (const [name, fallback] of Object.entries({ createDestination: created, updateDestination: fixtures.destinations[0], verifyDestination: fixtures.destinations[1] })) {
      api[name] = async (...args) => {
        calls.push({ name, args });
        return overrides[name] ? overrides[name](...args) : fallback;
      };
    }
    const { useDiscordConnection } = loadSource("src/components/dashboard/useDiscordConnection.ts", {
      react: hooks, "@/lib/api": { ApiError }, "@/lib/dashboard-api": api,
    });
    return () => useDiscordConnection(owner.value);
  });
  return { owner, hook, calls, unmount() { hook.unmount(); owner.unmount(); } };
}

test("mount/replay/refresh never send messages; create adopts metadata and explicit tests reuse IDs", async () => {
  const app = await setup();
  app.hook.replayEffects();
  await app.owner.value.retryDestinations();
  await flush();
  assert.equal(app.calls.length, 0);
  assert.equal(await app.hook.value.run({ kind: "create", input: { label: "New channel", webhook_url: secret } }), "saved");
  await flush();
  assert.equal(app.owner.value.destinations.data.length, 3);
  assert.equal(app.owner.value.destinations.data.at(-1).id, "new-id");
  assert.match(app.hook.value.createResult.message, /Destination saved/);
  await app.hook.value.run({ kind: "test", id: fixtures.destinations[1].id });
  await flush();
  assert.equal(app.owner.value.destinations.data.length, 3);
  assert.equal(app.calls.length, 2);
  assert.equal(app.calls[1].name, "verifyDestination");
  assert.equal(app.calls[1].args[1], fixtures.destinations[1].id);
  assert.notEqual(app.calls[0].args[0], app.calls[1].args[0]);
  assert.match(app.hook.value.results[fixtures.destinations[1].id].test.message, /Test message sent/);
  assert.doesNotMatch(JSON.stringify(app.hook.value), /temporary-test-secret/);
  app.unmount();
});

test("duplicate clicks, replacement and collection refresh cannot overlap a test", async () => {
  const response = deferred();
  const app = await setup({ verifyDestination: () => response.promise });
  const id = fixtures.destinations[1].id;
  const run = app.hook.value.run;
  const pending = run({ kind: "test", id });
  assert.equal(await run({ kind: "test", id }), "ignored");
  assert.equal(await run({ kind: "replace", id, webhook_url: secret }), "ignored");
  const reads = app.owner.calls.length;
  assert.equal(await app.owner.value.retryDestinations(), false);
  await flush();
  assert.equal(app.owner.value.destinationMutationPending, true);
  assert.equal(app.owner.calls.length, reads);
  assert.equal(app.calls.length, 1);
  response.resolve(fixtures.destinations[1]);
  await pending;
  await flush();
  assert.equal(app.owner.value.destinationMutationPending, false);
  app.unmount();
});

test("replacement retains the ID, resets verification, clears an old test result and blocks tests until completion", async () => {
  const response = deferred();
  const id = fixtures.destinations[1].id;
  const app = await setup({ updateDestination: () => response.promise });
  await app.hook.value.run({ kind: "test", id });
  await flush();
  const pending = app.hook.value.run({ kind: "replace", id, webhook_url: secret });
  assert.equal(await app.hook.value.run({ kind: "test", id }), "ignored");
  response.resolve({ ...fixtures.destinations[1], verified_at: null });
  await pending;
  await flush();
  assert.equal(app.owner.value.destinations.data.find((d) => d.id === id).verified_at, null);
  assert.equal(app.owner.value.destinations.data.length, 2);
  assert.equal(app.hook.value.results[id].test, undefined);
  assert.match(app.hook.value.results[id].save.message, /Webhook replaced/);
  await app.hook.value.run({ kind: "test", id });
  await flush();
  assert.deepEqual(app.calls.map((call) => call.name), ["verifyDestination", "updateDestination", "verifyDestination"]);
  app.unmount();
});

test("validation and duplicate-label errors retain correctable forms with safe copy", async () => {
  for (const [status, code, text] of [[409, "destination_label_exists", /already uses this label/], [422, "invalid_webhook_url", /valid Discord webhook URL/], [422, "validation_error", /120 characters/]]) {
    const app = await setup({ createDestination: () => { throw failure(status, code); } });
    assert.equal(await app.hook.value.run({ kind: "create", input: { label: "New channel", webhook_url: secret } }), "failed");
    await flush();
    assert.match(app.hook.value.createResult.message, text);
    assert.doesNotMatch(app.hook.value.createResult.message, /temporary-test-secret/);
    assert.equal(app.owner.value.destinations.data.length, 2);
    assert.equal(app.owner.calls.filter((call) => call.name === "destinations").length, 1);
    app.unmount();
  }
});

test("test failures remain visible beside historical verification and distinguish application outages", async () => {
  for (const [error, text] of [
    [failure(422, "webhook_rejected"), /Discord rejected/],
    [failure(502, "webhook_verification_failed"), /server could not verify/],
    [failure(503, "webhook_unavailable"), /Discord could not confirm/],
    [failure(503, "authentication_unavailable"), /application service/],
    [new TypeError(`Timeout: ${secret}`), /could not be confirmed.*may have arrived/],
  ]) {
    const app = await setup({ verifyDestination: () => { throw error; } });
    const id = fixtures.destinations[1].id;
    await app.hook.value.run({ kind: "test", id });
    await flush();
    await app.owner.value.retryDestinations();
    await flush();
    assert.equal(app.owner.value.destinations.data[1].verified_at, fixtures.destinations[1].verified_at);
    assert.match(app.hook.value.results[id].test.message, text);
    assert.doesNotMatch(app.hook.value.results[id].test.message, /temporary-test-secret/);
    assert.equal(app.calls.length, 1);
    app.unmount();
  }
});

test("ambiguous create and replacement refresh metadata under the mutation gate without retrying writes", async () => {
  for (const operation of [{ kind: "create", input: { label: created.label, webhook_url: secret } }, { kind: "replace", id: fixtures.destinations[1].id, webhook_url: secret }]) {
    const refresh = deferred();
    let reads = 0;
    const app = await setup({ createDestination: () => { throw new TypeError("Lost response"); }, updateDestination: () => { throw failure(502, "unknown"); } }, {
      destinations: () => ++reads === 1 ? fixtures.destinations : refresh.promise,
    });
    const pending = app.hook.value.run(operation);
    await flush();
    assert.equal(app.owner.value.destinationMutationPending, true);
    assert.equal(reads, 2);
    assert.equal(await app.hook.value.run(operation), "ignored");
    refresh.resolve([...fixtures.destinations, created]);
    assert.equal(await pending, "uncertain");
    await flush();
    assert.equal(app.calls.length, 1);
    assert.equal(app.owner.value.destinationMutationPending, false);
    const result = operation.kind === "create" ? app.hook.value.createResult : app.hook.value.results[operation.id].save;
    assert.match(result.message, /could not be confirmed/);
    assert.match(result.message, operation.kind === "create" ? /Check the labels below/ : /cannot reveal which URL/);
    app.unmount();
  }
});

test("failed ambiguous-write reconciliation blocks another save until metadata refresh succeeds", async () => {
  let reads = 0;
  const app = await setup({ createDestination: () => { throw new TypeError("Lost response"); } }, {
    destinations: () => { if (++reads === 2) throw new TypeError("Offline"); return fixtures.destinations; },
  });
  const operation = { kind: "create", input: { label: created.label, webhook_url: secret } };
  await app.hook.value.run(operation);
  await flush();
  app.hook.render();
  assert.equal(app.owner.value.destinations.status, "error");
  assert.equal(await app.hook.value.run(operation), "ignored");
  assert.match(app.hook.value.createResult.message, /Refresh destinations successfully/);
  await app.owner.value.retryDestinations();
  await flush();
  app.hook.render();
  assert.equal(await app.hook.value.run(operation), "uncertain");
  assert.equal(app.calls.length, 2);
  app.unmount();
});

test("401/403 use account access handling and do not retain tenant metadata", async () => {
  for (const status of [401, 403]) {
    const app = await setup({ verifyDestination: () => { throw failure(status, "authentication_required"); } });
    await app.hook.value.run({ kind: "test", id: fixtures.destinations[0].id });
    await flush();
    assert.equal(app.owner.value.access.status, "denied");
    assert.equal(app.owner.value.destinations.data, null);
    assert.equal(app.hook.value.results[fixtures.destinations[0].id], undefined);
    app.unmount();
  }
});

test("unmount/access loss aborts mutations and ignored cancellation cannot adopt late responses", async () => {
  for (const end of ["unmount", "access"]) {
    const response = deferred();
    const app = await setup({ createDestination: () => response.promise });
    const pending = app.hook.value.run({ kind: "create", input: { label: created.label, webhook_url: secret } });
    await flush();
    const signal = app.calls[0].args.at(-1).signal;
    if (end === "unmount") app.unmount();
    else app.owner.value.reportAccessFailure(failure(401, "authentication_required"));
    assert.equal(signal.aborted, true);
    response.resolve(created);
    assert.equal(await pending, "ignored");
    await flush();
    assert.equal(app.hook.settersAfterUnmount, 0);
    assert.equal(app.owner.settersAfterUnmount, 0);
    if (end === "access") {
      assert.equal(app.owner.value.destinations.data, null);
      app.unmount();
    }
  }
});

function panelFixture(actions = {}, state = {}) {
  const sheet = loadSource("src/components/marketing/Sheet.tsx");
  const modules = {
    "@/components/marketing/Sheet": sheet,
    "./useDiscordConnection": { useDiscordConnection: () => ({ results: {}, pending: null, ...actions }) },
  };
  const props = { state: { destinations: { status: "loaded", data: fixtures.destinations }, destinationMutationPending: false, ...state } };
  const { DiscordConnectionPanel } = loadSource("src/components/dashboard/DiscordConnectionPanel.tsx", modules);
  return { modules, props, html: renderToStaticMarkup(React.createElement(DiscordConnectionPanel, props)) };
}

test("panel shows all destinations, distinct current failure and historical verification, and accessible masked forms", () => {
  const { html } = panelFixture({ results: { [fixtures.destinations[1].id]: { test: { status: "error", message: "Discord rejected this webhook." } } } });
  assert.match(html, /Collectibles/);
  assert.match(html, /Games/);
  assert.match(html, /Previously verified:/);
  assert.match(html, /historical verification/);
  assert.match(html, /role="alert"[^>]*>Discord rejected/);
  assert.match(html, /type="password"/);
  assert.match(html, /maxLength="120"/);
  assert.match(html, /maxLength="2048"/);
  assert.match(html, /for="new-destination-url"/);
  assert.match(html, /autoComplete="off"/);
  assert.doesNotMatch(html, /last checked|Connected|temporary-test-secret/);
  const busy = panelFixture({ pending: { kind: "test", id: fixtures.destinations[1].id } }, { destinationMutationPending: true }).html;
  assert.equal((busy.match(/<button[^>]*disabled=""/g) ?? []).length, 6);
});

function elements(node, type) {
  if (!node || typeof node !== "object") return [];
  const children = React.Children.toArray(node.props?.children);
  return [...(node.type === type ? [node] : []), ...children.flatMap((child) => elements(child, type))];
}

function mountForm(onSave, create = true) {
  const { modules } = panelFixture();
  return mountHook((hooks) => {
    const { DiscordWebhookForm } = loadSource("src/components/dashboard/DiscordConnectionPanel.tsx", { ...modules, react: { ...React, ...hooks } });
    return () => DiscordWebhookForm({ id: "form", create, disabled: false, pending: false, onSave });
  });
}

test("form rejects blanks and bounds, preserves rejected input, clears successful/uncertain secrets and unmounts safely", async () => {
  for (const outcome of ["saved", "failed", "uncertain"]) {
    const calls = [];
    const form = mountForm(async (...args) => { calls.push(args); return outcome; });
    const submit = async () => { form.value.props.onSubmit({ preventDefault() {} }); await flush(); };
    await submit();
    assert.equal(calls.length, 0);
    assert.match(renderToStaticMarkup(form.value), /Enter a destination label/);
    for (const [label, url] of [["x".repeat(121), secret], ["Valid", " "], ["Valid", "x".repeat(2049)], ["Valid", secret]]) {
      const inputs = elements(form.value, "input");
      inputs[0].props.onChange({ target: { value: label } });
      inputs[1].props.onChange({ target: { value: url } });
      await flush();
      await submit();
    }
    assert.equal(calls.length, 1);
    assert.equal(elements(form.value, "input")[1].props.value, outcome === "failed" ? secret : "");
    form.unmount();
  }
  const response = deferred();
  const form = mountForm(() => response.promise, false);
  elements(form.value, "input")[0].props.onChange({ target: { value: secret } });
  await flush();
  form.value.props.onSubmit({ preventDefault() {} });
  form.unmount();
  response.resolve("saved");
  await flush();
  assert.equal(form.settersAfterUnmount, 0);
  const fresh = mountForm(async () => "saved", false);
  assert.equal(elements(fresh.value, "input")[0].props.value, "");
  fresh.unmount();
});
