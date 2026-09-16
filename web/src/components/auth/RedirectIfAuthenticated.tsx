"use client";

import { useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";

import { getCurrentUser } from "@/lib/auth-api";

export function RedirectIfAuthenticated() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    // Future reset/verification pages must remain accessible with a session.
    if (pathname !== "/login" && pathname !== "/signup") return;
    let cancelled = false;

    getCurrentUser().then((user) => {
      if (!cancelled && user !== null) router.replace("/dashboard");
    }).catch(() => {
      // An unavailable API cannot confirm a session. Leave the form usable.
    });

    return () => { cancelled = true; };
  }, [pathname, router]);

  return null;
}
