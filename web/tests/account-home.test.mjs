import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
const source = readFileSync(new URL("../src/components/auth/AccountHome.tsx", import.meta.url), "utf8");
const compiled = ts.transpileModule(source, {
  compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
}).outputText;

async function renderAccount(apiBase) {
  const effects = [];
  const tokensRequested = [];
  const apiCalls = [];
  const modules = {
    react: { ...React, useEffect: (callback) => effects.push(callback) },
    "next/navigation": { useSearchParams: () => new URLSearchParams("welcome=1") },
    "@clerk/nextjs": {
      useAuth: () => ({
        isLoaded: true,
        userId: "user_fixture",
        getToken: async () => { tokensRequested.push(true); return "test-session-token"; },
      }),
      useUser: () => ({ user: { primaryEmailAddress: { emailAddress: "person@example.com" } } }),
      UserButton: () => React.createElement("button", null, "Profile"),
      SignOutButton: ({ children }) => children,
    },
    "@/lib/auth-api": {
      getCurrentUser: async (token) => { apiCalls.push(token); return { id: "account_fixture" }; },
    },
    "@/lib/api": { ApiError: class extends Error {} },
    "./AuthHeading": { AuthHeading: ({ children }) => React.createElement("h1", null, children) },
  };
  const exports = {};
  runInNewContext(compiled, {
    exports,
    process: { env: { NEXT_PUBLIC_API_BASE_URL: apiBase } },
    require: (name) => modules[name] ?? require(name),
  });
  const html = renderToStaticMarkup(React.createElement(exports.AccountHome));
  effects.forEach((callback) => callback());
  await Promise.resolve();
  await Promise.resolve();
  return { html, tokensRequested, apiCalls };
}

test("a frontend-only account shows Clerk profile controls without requesting an API token", async () => {
  for (const apiBase of [undefined, "", "   "]) {
    const { html, tokensRequested, apiCalls } = await renderAccount(apiBase);
    assert.match(html, /person@example.com/);
    assert.match(html, /You’re signed in/);
    assert.match(html, /Use your profile menu/);
    assert.doesNotMatch(html, /Loading your account|role="alert"|Your account is ready/);
    assert.deepEqual(tokensRequested, []);
    assert.deepEqual(apiCalls, []);
  }
});

test("configuring the API still loads the application account using a Clerk token", async () => {
  const { html, tokensRequested, apiCalls } = await renderAccount("https://api.example.com/api/v1");
  assert.match(html, /Loading your account/);
  assert.equal(tokensRequested.length, 1);
  assert.deepEqual(apiCalls, ["test-session-token"]);
});
