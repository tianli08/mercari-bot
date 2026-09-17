import type { SignInFutureResource } from "@clerk/nextjs/types";

export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 128;
export const RESET_CONFIRMATION =
  "If an account with a password exists for that address, a reset code is on its way. Check your inbox and spam folder.";
export const INVALID_CODE = "That code is invalid or expired. Try again or request a new code.";

function errorDetails(error: unknown): { code?: string; status?: number; retryAfter?: number } {
  if (!error || typeof error !== "object") return {};
  const value = error as { code?: string; status?: number; retryAfter?: number; errors?: { code?: string }[] };
  return { ...value, code: value.errors?.[0]?.code ?? value.code };
}

export function recoveryErrorMessage(error: unknown): string {
  const { code, status, retryAfter } = errorDetails(error);
  if (status === 429 || code?.startsWith("too_many_requests")) {
    return typeof retryAfter === "number" && Number.isFinite(retryAfter) && retryAfter > 0
      ? `Too many attempts. Please try again in ${Math.ceil(retryAfter)} seconds.`
      : "Too many attempts. Please wait a moment before trying again.";
  }
  if (["form_code_incorrect", "verification_expired", "verification_failed", "verification_invalid", "verification_attempts_exceeded"].includes(code ?? "")) {
    return INVALID_CODE;
  }
  if (["form_password_pwned", "form_password_not_strong_enough", "form_password_validation_failed"].includes(code ?? "")) {
    return "Choose a stronger password that you haven’t used elsewhere.";
  }
  if (code === "form_password_length_too_short") return `Use at least ${MIN_PASSWORD_LENGTH} characters for your password.`;
  return "We couldn’t complete that request. Please try again.";
}

export function passwordValidationError(password: string): string | undefined {
  if (password.length < MIN_PASSWORD_LENGTH || password.length > MAX_PASSWORD_LENGTH) {
    return `Use between ${MIN_PASSWORD_LENGTH} and ${MAX_PASSWORD_LENGTH} characters for your password.`;
  }
}

// Clerk owns recovery. Never call the retired application password/token endpoints.
export async function requestPasswordReset(signIn: SignInFutureResource, email: string): Promise<void> {
  const reset = await signIn.reset();
  if (reset.error) throw reset.error;
  try {
    const created = await signIn.create({ identifier: email.trim() });
    if (created.error) throw created.error;
    // Social-only accounts and unknown accounts receive the same confirmation.
    if (!signIn.supportedFirstFactors.some((factor) => factor.strategy === "reset_password_email_code")) return;
    const sent = await signIn.resetPasswordEmailCode.sendCode();
    if (sent.error) throw sent.error;
  } catch (error) {
    if (errorDetails(error).code === "form_identifier_not_found") return;
    throw error;
  }
}

export function hasPasswordResetAttempt(signIn: SignInFutureResource): boolean {
  return signIn.firstFactorVerification.strategy === "reset_password_email_code" &&
    ["needs_first_factor", "needs_new_password"].includes(signIn.status);
}

export async function confirmPasswordReset(signIn: SignInFutureResource, password: string): Promise<void> {
  const validation = passwordValidationError(password);
  if (validation) throw new Error(validation);
  if (!hasPasswordResetAttempt(signIn) || signIn.status !== "needs_new_password") {
    throw new Error("A verified password reset code is required.");
  }
  const result = await signIn.resetPasswordEmailCode.submitPassword({
    password,
    signOutOfOtherSessions: true,
  });
  if (result.error) throw result.error;
  // Do not finalize/activate a session. The user logs in with their new password,
  // including any MFA or device checks handled by the existing Clerk SignIn UI.
}
