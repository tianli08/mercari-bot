import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

function compile(relativePath) {
  const source = readFileSync(new URL(relativePath, import.meta.url), "utf8");
  return ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
  }).outputText;
}

const transportSource = compile("../src/lib/api.ts");
const dashboardSource = compile("../src/lib/dashboard-api.ts");
const fixtures = {};
runInNewContext(compile("./fixtures/dashboard-responses.ts"), { exports: fixtures });
// Compare JSON data across the isolated module contexts without prototype differences.
const { destinations, watchlists } = JSON.parse(JSON.stringify(fixtures));
const plain = (value) => JSON.parse(JSON.stringify(value));

function loadClient(fetch, base = "https://api.example.com/api/v1") {
  const transport = {};
  runInNewContext(transportSource, {
    exports: transport,
    fetch,
    URL,
    process: { env: { NEXT_PUBLIC_API_BASE_URL: base } },
  });
  const client = {};
  runInNewContext(dashboardSource, {
    exports: client,
    require: (name) => {
      assert.equal(name, "./api");
      return transport;
    },
  });
  return { ...client, ApiError: transport.ApiError };
}

const resources = [
  { method: "listDestinations", path: "/destinations", records: destinations },
  { method: "listWatchlists", path: "/watchlists", records: watchlists },
];

for (const { method, path, records } of resources) {
  test(`${method} preserves API prefixes and sends the current token without cookies or ownership`, async () => {
    for (const base of ["https://api.example.com/api/v1", "https://api.example.com/gateway/api/v1/"]) {
      const calls = [];
      const client = loadClient(async (url, init) => {
        calls.push({ url, init });
        return Response.json(records);
      }, base);

      for (const token of ["first-session-token", "current-session-token"]) {
        assert.deepEqual(plain(await client[method](token)), records);
        const { url, init } = calls.at(-1);
        assert.equal(url, `${base.replace(/\/$/, "")}${path}`);
        assert.equal(init.method ?? "GET", "GET");
        assert.equal(init.cache, "no-store");
        assert.equal(init.credentials, "omit");
        assert.equal(init.body, undefined);
        assert.equal(init.signal, undefined);
        assert.deepEqual([...new Headers(init.headers)], [["authorization", `Bearer ${token}`]]);
      }
      assert.equal(calls.length, 2);
    }
  });

  test(`${method} returns a successful empty collection`, async () => {
    const client = loadClient(async () => Response.json([]));
    assert.deepEqual(await client[method]("session-token"), []);
  });

  test(`${method} preserves 401, 403, and 503 API errors`, async () => {
    for (const [status, code, detail] of [
      [401, "authentication_required", "Authentication required"],
      [403, "account_unavailable", "Account unavailable"],
      [503, "authentication_unavailable", "Authentication temporarily unavailable"],
    ]) {
      const client = loadClient(async () => Response.json({ code, detail }, { status }));
      await assert.rejects(client[method]("session-token"), (error) => {
        assert.ok(error instanceof client.ApiError);
        assert.equal(error.status, status);
        assert.equal(error.code, code);
        assert.equal(error.detail, detail);
        return true;
      });
    }
  });

  test(`${method} propagates network failures`, async () => {
    const failure = new TypeError("Failed to fetch");
    const client = loadClient(async () => { throw failure; });
    await assert.rejects(client[method]("session-token"), (error) => error === failure);
  });

  test(`${method} rejects malformed collections and missing response bodies`, async () => {
    for (const body of [null, {}, { items: [] }, "", [null], [{}], [...records, null]]) {
      const client = loadClient(async () => Response.json(body));
      await assert.rejects(client[method]("session-token"), /Invalid .* response/);
    }
    const noContent = loadClient(async () => new Response(null, { status: 204 }));
    await assert.rejects(noContent[method]("session-token"), /Invalid .* response/);

    const invalidJson = loadClient(async () => new Response("<html>unavailable</html>"));
    await assert.rejects(invalidJson[method]("session-token"), { name: "SyntaxError" });
  });

  test(`${method} forwards cancellation and preserves the abort error`, async () => {
    for (const alreadyAborted of [false, true]) {
      const controller = new AbortController();
      if (alreadyAborted) controller.abort();
      const client = loadClient((_url, { signal }) => {
        assert.equal(signal, controller.signal);
        return new Promise((_resolve, reject) => {
          if (signal.aborted) reject(signal.reason);
          else signal.addEventListener("abort", () => reject(signal.reason), { once: true });
        });
      });
      const pending = client[method]("session-token", { signal: controller.signal });
      controller.abort();
      await assert.rejects(pending, (error) => error === controller.signal.reason);
    }
  });

  test(`${method} reports missing API configuration without making a request`, async () => {
    const client = loadClient(() => assert.fail("No API is configured"), "");
    await assert.rejects(client[method]("session-token"), /NEXT_PUBLIC_API_BASE_URL is not set/);
  });
}

test("destination reads reject malformed metadata instead of exposing it as a usable connection", async () => {
  for (const patch of [{ type: "email" }, { verified_at: undefined }, { label: null }, { created_at: 123 }]) {
    const client = loadClient(async () => Response.json([{ ...destinations[0], ...patch }]));
    await assert.rejects(client.listDestinations("session-token"), /Invalid destinations response/);
  }
});

test("watchlist reads reject malformed keywords, filters, and monitoring state", async () => {
  for (const patch of [
    { keywords: [42] },
    { enabled: "false" },
    { destination_id: null },
    { filters: null },
    { filters: { min_price: null, max_price: null, condition: "new" } },
    { filters: { min_price: "500", max_price: null, condition: "any" } },
    { filters: { min_price: 0.5, max_price: null, condition: "any" } },
    { filters: { min_price: null, condition: "any" } },
  ]) {
    const client = loadClient(async () => Response.json([{ ...watchlists[0], ...patch }]));
    await assert.rejects(client.listWatchlists("session-token"), /Invalid watchlists response/);
  }
});

const webhook = "https://discord.com/api/webhooks/123/temporary-test-secret";
const writes = [
  { name: "createDestination", method: "POST", path: "/destinations", args: [{ label: "New channel", webhook_url: webhook, owner_id: "ignored" }], body: { label: "New channel", webhook_url: webhook } },
  { name: "updateDestination", method: "PATCH", path: "/destinations/id%2Fwith%20space", args: ["id/with space", { webhook_url: webhook, owner_id: "ignored" }], body: { webhook_url: webhook } },
  { name: "verifyDestination", method: "POST", path: "/destinations/id%2Fwith%20space/verify", args: ["id/with space"] },
];

for (const { name, method, path, args, body } of writes) {
  test(`${name} sends one authenticated backend request and returns only public metadata`, async () => {
    const signal = new AbortController().signal;
    let requests = 0;
    const client = loadClient(async (url, init) => {
      requests++;
      assert.equal(url, `https://api.example.com/gateway/api/v1${path}`);
      assert.equal(init.method, method);
      assert.equal(init.credentials, "omit");
      assert.equal(init.cache, "no-store");
      assert.equal(init.signal, signal);
      assert.equal(new Headers(init.headers).get("authorization"), "Bearer current-token");
      assert.equal(new Headers(init.headers).get("content-type"), body ? "application/json" : null);
      assert.deepEqual(init.body ? JSON.parse(init.body) : undefined, body);
      return Response.json({ ...destinations[0], webhook_url: webhook, owner_id: "private" });
    }, "https://api.example.com/gateway/api/v1/");
    assert.deepEqual(plain(await client[name]("current-token", ...args, { signal })), destinations[0]);
    assert.equal(requests, 1);
  });

  test(`${name} propagates contract errors and ambiguous failures without retries`, async () => {
    for (const [status, code] of [[401, "authentication_required"], [403, "account_unavailable"], [409, "destination_label_exists"], [422, "invalid_webhook_url"], [422, "webhook_rejected"], [502, "webhook_verification_failed"], [503, "webhook_unavailable"]]) {
      let requests = 0;
      const client = loadClient(async () => { requests++; return Response.json({ code, detail: "Controlled failure" }, { status }); });
      await assert.rejects(client[name]("token", ...args), (error) => error instanceof client.ApiError && error.status === status && error.code === code);
      assert.equal(requests, 1);
    }
    for (const response of [null, {}, { ...destinations[0], verified_at: 42 }]) {
      const client = loadClient(async () => Response.json(response));
      await assert.rejects(client[name]("token", ...args), /Invalid destination response/);
    }
    let requests = 0;
    const failure = new TypeError("Connection lost");
    const client = loadClient(async () => { requests++; throw failure; });
    await assert.rejects(client[name]("token", ...args), (error) => error === failure);
    assert.equal(requests, 1);
  });
}

test("destination list strips unexpected private fields before they reach the dashboard", async () => {
  const client = loadClient(async () => Response.json(destinations.map((item) => ({ ...item, webhook_url: webhook }))));
  assert.deepEqual(plain(await client.listDestinations("token")), destinations);
});

test("destination updates support label-only changes without adding a URL", async () => {
  const client = loadClient(async (_url, init) => {
    assert.deepEqual(JSON.parse(init.body), { label: "Renamed" });
    return Response.json({ ...destinations[0], label: "Renamed" });
  });
  assert.equal((await client.updateDestination("token", "id", { label: "Renamed" })).label, "Renamed");
});
