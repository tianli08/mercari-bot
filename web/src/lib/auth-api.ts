import { ApiError, apiFetch } from "./api";

// Session cookie is HttpOnly + SameSite=Lax. In development the API base URL
// must use http://localhost:8000 (never 127.0.0.1) so the browser treats the
// Next.js origin and the API as same-site and attaches the cookie.

export const MIN_PASSWORD_LENGTH = 12;
export const MAX_PASSWORD_LENGTH = 128;

export type PublicUser = {
  id: string;
  email: string;
  status: "active" | "pending" | "suspended";
  plan: "free";
};

type AuthCredentials = {
  email: string;
  password: string;
};

function jsonPost(body: AuthCredentials): RequestInit {
  return {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  };
}

export function signup(email: string, password: string): Promise<PublicUser> {
  return apiFetch<PublicUser>("/auth/signup", jsonPost({ email, password }));
}

export function login(email: string, password: string): Promise<PublicUser> {
  return apiFetch<PublicUser>("/auth/login", jsonPost({ email, password }));
}

export async function logout(): Promise<void> {
  await apiFetch<void>("/auth/logout", { method: "POST" });
}

export async function getCurrentUser(): Promise<PublicUser | null> {
  try {
    return await apiFetch<PublicUser>("/auth/me");
  } catch (error) {
    if (error instanceof ApiError && error.status === 401) {
      return null;
    }
    throw error;
  }
}
