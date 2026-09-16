"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";

import { logout } from "@/lib/auth-api";
import { PRIMARY_BUTTON_CLASS_NAME } from "@/lib/ui-styles";

export function LogoutButton() {
  const router = useRouter();
  const [pending, setPending] = useState(false);

  async function handleLogout() {
    if (pending) return;
    setPending(true);
    try {
      await logout();
    } catch {
      // Return to login even if logout fails; the session also expires server-side.
    } finally {
      router.replace("/login");
    }
  }

  return (
    <button
      type="button"
      onClick={handleLogout}
      disabled={pending}
      aria-busy={pending}
      className={`${PRIMARY_BUTTON_CLASS_NAME} rounded-none uppercase focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-ink disabled:cursor-not-allowed disabled:opacity-50`}
    >
      {pending ? <span role="status">Please wait…</span> : "[ Log out ]"}
    </button>
  );
}
