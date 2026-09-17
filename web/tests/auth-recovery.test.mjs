import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { createRequire } from "node:module";
import test from "node:test";
import { runInNewContext } from "node:vm";
import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import ts from "typescript";

const require = createRequire(import.meta.url);
function loadSource(path, modules = {}) {
  const source = readFileSync(new URL(`../src/${path}`, import.meta.url), "utf8");
  const compiled = ts.transpileModule(source, {
    compilerOptions: { module: ts.ModuleKind.CommonJS, jsx: ts.JsxEmit.ReactJSX, target: ts.ScriptTarget.ES2020 },
  }).outputText;
  const exports = {};
  runInNewContext(compiled, { exports, require: (name) => modules[name] ?? require(name) });
  return exports;
}

const recovery = loadSource("lib/auth-recovery.ts");
const apiError = (code, extra = {}) => ({ errors: [{ code }], ...extra });

function signInFixture(options = {}) {
  const calls = [];
  const signIn = {
    status: "needs_new_password",
    firstFactorVerification: { strategy: "reset_password_email_code" },
    supportedFirstFactors: [{ strategy: "reset_password_email_code" }],
    reset: async () => { calls.push(["reset"]); return { error: null }; },
    create: async (params) => { calls.push(["create", { ...params }]); return { error: options.createError ?? null }; },
    resetPasswordEmailCode: {
      sendCode: async () => { calls.push(["send"]); return { error: options.sendError ?? null }; },
      submitPassword: async (params) => { calls.push(["password", { ...params }]); return { error: options.passwordError ?? null }; },
    },
    finalize: async () => { assert.fail("Recovery must never activate a session"); },
  };
  return { signIn, calls };
}

test("requesting recovery clears any previous account and sends the code through Clerk", async () => {
  const { signIn, calls } = signInFixture();
  assert.equal(await recovery.requestPasswordReset(signIn, "  person@example.com  "), undefined);
  assert.deepEqual(calls, [["reset"], ["create", { identifier: "person@example.com" }], ["send"]]);
});

test("unknown and social-only accounts return the same result as an eligible account", async () => {
  for (const fixture of [signInFixture(), signInFixture({ createError: apiError("form_identifier_not_found") }), signInFixture({ createError: { code: "form_identifier_not_found" } })]) {
    assert.equal(await recovery.requestPasswordReset(fixture.signIn, "person@example.com"), undefined);
  }
  const { signIn, calls } = signInFixture();
  signIn.supportedFirstFactors = [{ strategy: "oauth_google" }];
  assert.equal(await recovery.requestPasswordReset(signIn, "person@example.com"), undefined);
  assert.equal(calls.some(([name]) => name === "send"), false);
});

test("network failures and throttling are not disguised as successful sends", async () => {
  for (const error of [new Error("offline"), apiError("too_many_requests", { status: 429, retryAfter: 45 })]) {
    for (const stage of ["createError", "sendError"]) {
      const { signIn } = signInFixture({ [stage]: error });
      await assert.rejects(recovery.requestPasswordReset(signIn, "person@example.com"), (actual) => actual === error);
    }
  }
});

test("password reset requires a verified recovery attempt and honors both password bounds", async () => {
  for (const length of [0, 11, 129]) {
    const { signIn, calls } = signInFixture();
    await assert.rejects(recovery.confirmPasswordReset(signIn, "x".repeat(length)), /between 12 and 128/);
    assert.deepEqual(calls, []);
  }
  for (const status of ["needs_identifier", "needs_first_factor", "complete", "needs_second_factor"]) {
    const { signIn, calls } = signInFixture();
    signIn.status = status;
    await assert.rejects(recovery.confirmPasswordReset(signIn, "x".repeat(12)), /verified password reset code/);
    assert.deepEqual(calls, []);
  }
  const { signIn } = signInFixture();
  signIn.firstFactorVerification.strategy = "email_code";
  await assert.rejects(recovery.confirmPasswordReset(signIn, "x".repeat(12)), /verified password reset code/);
});

test("a successful reset invalidates other sessions and never finalizes a sign-in", async () => {
  for (const length of [12, 128]) {
    const { signIn, calls } = signInFixture();
    const password = "x".repeat(length);
    await recovery.confirmPasswordReset(signIn, password);
    assert.deepEqual(calls, [["password", { password, signOutOfOtherSessions: true }]]);
  }
  const error = apiError("form_password_pwned");
  await assert.rejects(recovery.confirmPasswordReset(signInFixture({ passwordError: error }).signIn, "x".repeat(12)), (actual) => actual === error);
});

test("errors expose safe retry and validation copy, never raw provider messages", () => {
  assert.equal(recovery.recoveryErrorMessage(apiError("too_many_requests", { status: 429, retryAfter: 12.2 })), "Too many attempts. Please try again in 13 seconds.");
  assert.match(recovery.recoveryErrorMessage({ code: "too_many_requests" }), /wait a moment/);
  for (const retryAfter of [-1, NaN, Infinity]) {
    assert.match(recovery.recoveryErrorMessage({ status: 429, retryAfter }), /wait a moment/);
  }
  for (const code of ["form_code_incorrect", "verification_expired", "verification_failed"]) {
    assert.equal(recovery.recoveryErrorMessage(apiError(code)), recovery.INVALID_CODE);
  }
  assert.match(recovery.recoveryErrorMessage(apiError("form_password_pwned")), /stronger password/);
  for (const error of [null, undefined, new Error("secret token"), { message: "person@example.com" }]) {
    assert.equal(recovery.recoveryErrorMessage(error), "We couldn’t complete that request. Please try again.");
  }
});

function renderScreen(component, { query = "", loaded = true, signedIn = false, user = null, signIn = signInFixture().signIn } = {}) {
  const modules = {
    "@/lib/auth-recovery": recovery,
    "@clerk/nextjs": {
      useAuth: () => ({ isLoaded: loaded, isSignedIn: signedIn }),
      useSignIn: () => ({ signIn }),
      useUser: () => ({ isLoaded: loaded, user }),
    },
    "next/navigation": { useSearchParams: () => new URLSearchParams(query), useRouter: () => ({ push() { assert.fail("No navigation on mount"); } }) },
    "next/link": { default: ({ children, ...props }) => React.createElement("a", props, children) },
    "./AuthHeading": { AuthHeading: ({ children }) => React.createElement("h1", null, children) },
    "./FormField": loadSource("components/auth/FormField.tsx"),
    "./SubmitButton": { SubmitButton: ({ children, pending }) => React.createElement("button", { disabled: pending }, children) },
  };
  const exports = loadSource(`components/auth/${component}.tsx`, modules);
  return renderToStaticMarkup(React.createElement(exports[component]));
}

test("missing and legacy reset links show a fresh-code path, including while signed in", () => {
  for (const query of ["", "token=", "token=expired", "token=garbage&requested=1"]) {
    for (const signedIn of [false, true]) {
      const { signIn, calls } = signInFixture();
      signIn.status = "needs_identifier";
      const html = renderScreen("PasswordResetConfirmForm", { query, signIn, signedIn });
      assert.match(html, /invalid or expired/);
      assert.match(html, /href="\/reset-password"/);
      assert.doesNotMatch(html, /<form/);
      assert.deepEqual(calls, []);
    }
  }
});

test("real and unknown accounts render identical inbox confirmations", () => {
  const real = signInFixture().signIn;
  real.status = "needs_first_factor";
  const unknown = signInFixture().signIn;
  unknown.status = "needs_identifier";
  unknown.firstFactorVerification.strategy = null;
  const actual = renderScreen("PasswordResetConfirmForm", { query: "requested=1", signIn: real });
  assert.equal(actual, renderScreen("PasswordResetConfirmForm", { query: "requested=1", signIn: unknown }));
  assert.match(actual, /If an account with a password exists/);
  assert.match(actual, /autoComplete="one-time-code"/);
});

test("verified reset attempts resume the password form, without repeating verification on mount", () => {
  const { signIn, calls } = signInFixture();
  const html = renderScreen("PasswordResetConfirmForm", { signIn });
  assert.match(html, /New password/);
  assert.match(html, /minLength="12"/);
  assert.match(html, /maxLength="128"/);
  assert.deepEqual(calls, []);
});

test("verification resends are offered only for a signed-in unverified primary email", () => {
  const signedOut = renderScreen("EmailVerification");
  assert.match(signedOut, /Continue sign up/);
  assert.match(signedOut, /Log in to verify/);
  assert.doesNotMatch(signedOut, /<button|<form/);
  const html = renderScreen("EmailVerification", { user: { primaryEmailAddress: {
    id: "email_fixture", emailAddress: "person@example.com", verification: { status: "unverified" },
    prepareVerification() { assert.fail("Verification email must only be sent on explicit submit"); },
  } } });
  assert.match(html, /Send verification code/);
  assert.match(html, /person@example.com/);
});

test("verified email stays successful across fresh renders without consuming any token", () => {
  const user = { primaryEmailAddress: {
    id: "email_fixture", emailAddress: "person@example.com", verification: { status: "verified" },
    attemptVerification() { assert.fail("Already verified emails must not be verified again"); },
  } };
  for (let refresh = 0; refresh < 2; refresh++) {
    const html = renderScreen("EmailVerification", { user });
    assert.match(html, /Your email is verified/);
    assert.match(html, /href="\/dashboard"/);
    assert.doesNotMatch(html, /<form/);
  }
  const legacy = renderScreen("EmailVerification", { query: "token=old" });
  assert.match(legacy, /invalid or expired/);
});

test("signed-in recovery pages stay reachable and offer account management", () => {
  const html = renderScreen("PasswordResetRequestForm", { signedIn: true });
  assert.match(html, /already signed in/);
  assert.match(html, /href="\/dashboard"/);
  assert.doesNotMatch(html, /<form/);
});
