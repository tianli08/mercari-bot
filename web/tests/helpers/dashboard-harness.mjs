import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const require = createRequire(import.meta.url);
export function loadSource(path, modules = {}, env = {}) {
  const source = readFileSync(new URL(`../../${path}`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  runInNewContext(compiled, {
    exports, AbortController, DOMException,
    process: { env },
    require: (name) => modules[name] ?? require(name),
  });
  return exports;
}

export function deferred() {
  let resolve, reject;
  const promise = new Promise((yes, no) => { resolve = yes; reject = no; });
  return { promise, resolve, reject };
}
export const flush = () => new Promise((resolve) => setImmediate(resolve));
export const { ApiError } = loadSource("src/lib/api.ts");
export const fixtures = loadSource("tests/fixtures/dashboard-responses.ts");

// A small hook lifecycle driver for the existing Node runner. Render tests use
// React separately; this exercises asynchronous requests, cleanup and callbacks.
export function mountDashboard(overrides = {}) {
  const slots = [];
  let cursor = 0;
  let mounted = true;
  let pendingRender = false;
  let value;
  let settersAfterUnmount = 0;
  const effects = [];
  function schedule() {
    if (pendingRender) return;
    pendingRender = true;
    queueMicrotask(() => { pendingRender = false; if (mounted) RenderHook(); });
  }
  const hooks = {
    useState(initial) {
      const index = cursor++;
      if (!(index in slots)) slots[index] = typeof initial === "function" ? initial() : initial;
      return [slots[index], (update) => {
        if (!mounted) { settersAfterUnmount++; return; }
        slots[index] = typeof update === "function" ? update(slots[index]) : update;
        schedule();
      }];
    },
    useRef(initial) {
      const index = cursor++;
      return slots[index] ??= { current: initial };
    },
    useCallback(callback, deps) {
      const index = cursor++;
      if (!slots[index] || deps.some((dep, i) => !Object.is(dep, slots[index].deps[i]))) slots[index] = { callback, deps };
      return slots[index].callback;
    },
    useEffect(callback, deps) {
      const index = cursor++;
      if (!slots[index] || deps.some((dep, i) => !Object.is(dep, slots[index].deps[i]))) {
        const previous = slots[index];
        slots[index] = { callback, deps };
        effects.push(() => { previous?.cleanup?.(); slots[index].cleanup = callback(); });
      }
    },
  };
  const calls = [];
  let tokenNumber = 0;
  const getToken = overrides.getToken ?? (async () => `token-${++tokenNumber}`);
  function api(name, fallback) {
    return async (...args) => {
      calls.push({ name, token: args[0], signal: args[1]?.signal });
      return (overrides[name] ?? fallback)(...args);
    };
  }
  const { useDashboardState } = loadSource("src/components/dashboard/useDashboardState.ts", {
    react: hooks,
    "@/lib/api": { ApiError },
    "@/lib/auth-api": { getCurrentUser: api("account", async () => ({ id: "account-a", email: "a@example.com", status: "active", plan: "free" })) },
    "@/lib/dashboard-api": {
      listDestinations: api("destinations", async () => fixtures.destinations),
      listWatchlists: api("watchlists", async () => fixtures.watchlists),
    },
  });
  function RenderHook() {
    cursor = 0;
    value = useDashboardState(getToken);
    while (effects.length) effects.shift()();
  }
  RenderHook();
  return {
    get value() { return value; },
    get settersAfterUnmount() { return settersAfterUnmount; },
    calls,
    replayEffects() {
      for (const slot of slots) if (slot?.cleanup) { slot.cleanup(); slot.cleanup = slot.callback(); }
    },
    unmount() {
      mounted = false;
      for (const slot of slots) slot?.cleanup?.();
    },
  };
}
