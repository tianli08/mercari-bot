"use client";

import { Show, UserButton } from "@clerk/nextjs";
import Link from "next/link";

export function AuthControls() {
  return <>
    <Show when="signed-out">
      <Link href="/login" className="hover:opacity-70">Log in</Link>
      <Link href="/signup" className="border-b border-ink hover:opacity-70">Sign up</Link>
    </Show>
    <Show when="signed-in">
      <Link href="/dashboard" className="hover:opacity-70" prefetch={false}>Your account</Link>
      <UserButton />
    </Show>
  </>;
}
