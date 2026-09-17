import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import ts from "typescript";

const require = createRequire(import.meta.url);
const { PHASE_PRODUCTION_BUILD, PHASE_DEVELOPMENT_SERVER } = require("next/constants");
const source = readFileSync(new URL("../next.config.ts", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2020 },
}).outputText;

function loadConfig(env, phase = PHASE_PRODUCTION_BUILD) {
  const exports = {};
  runInNewContext(compiled, { exports, require, process: { env }, URL });
  return exports.default(phase);
}

const local = {
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_test_fixture",
  CLERK_SECRET_KEY: "sk_test_fixture",
  NEXT_PUBLIC_API_BASE_URL: "http://localhost:8000/api/v1",
};
const production = {
  VERCEL_ENV: "production",
  NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY: "pk_live_fixture",
  CLERK_SECRET_KEY: "sk_live_fixture",
  NEXT_PUBLIC_API_BASE_URL: "https://api.example.com/api/v1",
};

test("a build without hosting settings fails before it can be deployed", () => {
  assert.throws(() => loadConfig({}), /Missing deployment settings: NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY, CLERK_SECRET_KEY/);
  for (const name of ["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY"]) {
    assert.throws(() => loadConfig({ ...local, [name]: "   " }), new RegExp(name));
  }
});

test("frontend deployments do not require an application backend", () => {
  for (const value of [undefined, "", "   "]) {
    assert.equal(loadConfig({ ...production, NEXT_PUBLIC_API_BASE_URL: value }).reactCompiler, true);
  }
});

test("local builds accept development credentials and a local API", () => {
  assert.equal(loadConfig(local).reactCompiler, true);
});

test("development startup does not require production deployment settings", () => {
  assert.equal(loadConfig({}, PHASE_DEVELOPMENT_SERVER).reactCompiler, true);
});

test("production builds require both production credentials", () => {
  for (const name of ["NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY", "CLERK_SECRET_KEY"]) {
    assert.throws(() => loadConfig({ ...production, [name]: local[name] }), /require Clerk production keys/);
  }
});

test("invalid API settings fail without disclosing their values", () => {
  for (const value of ["not-a-url", "file:///private", "https://user:private-value@api.example.com"]) {
    assert.throws(() => loadConfig({ ...production, NEXT_PUBLIC_API_BASE_URL: value }), (error) => {
      assert.match(error.message, /NEXT_PUBLIC_API_BASE_URL/);
      assert.equal(error.message.includes(value), false);
      return true;
    });
  }
  for (const value of ["http://api.example.com", "https://localhost:8000", "https://127.0.0.1", "https://[::1]", "https://api.localhost"]) {
    assert.throws(() => loadConfig({ ...production, NEXT_PUBLIC_API_BASE_URL: value }), /deployed HTTPS API/);
  }
});

test("configured production builds retain the authentication redirects", async () => {
  const config = loadConfig(production);
  const redirects = await config.redirects();
  assert.equal(redirects.find((item) => item.source === "/sign-in/:path*").destination, "/login/:path*");
  assert.equal(redirects.find((item) => item.source === "/sign-up/:path*").destination, "/signup/:path*");
});
