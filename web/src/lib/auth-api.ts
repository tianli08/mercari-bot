import { apiFetch } from "./api";

export type PublicUser = {
  id: string;
  email: string;
  status: "active" | "pending" | "suspended";
  plan: "free";
};

export function getCurrentUser(token: string): Promise<PublicUser> {
  return apiFetch<PublicUser>("/auth/me", {
    cache: "no-store",
    headers: { Authorization: `Bearer ${token}` },
  });
}
