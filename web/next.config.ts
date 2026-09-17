import type { NextConfig } from "next";
import { PHASE_PRODUCTION_BUILD } from "next/constants";

function validateBuildEnvironment() {
  const required = [
    "NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY",
    "CLERK_SECRET_KEY",
  ] as const;
  const missing = required.filter((name) => !process.env[name]?.trim());

  if (missing.length > 0) {
    throw new Error(
      `Missing deployment settings: ${missing.join(", ")}. ` +
      "Set them in the hosting environment before building. Local environment files are not deployed.",
    );
  }

  if (process.env.VERCEL_ENV === "production") {
    if (
      !process.env.NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY!.startsWith("pk_live_") ||
      !process.env.CLERK_SECRET_KEY!.startsWith("sk_live_")
    ) {
      throw new Error("Production deployments require Clerk production keys in both Clerk settings.");
    }
  }

  const apiBase = process.env.NEXT_PUBLIC_API_BASE_URL?.trim();
  if (!apiBase) return;
  let apiUrl: URL;
  try {
    apiUrl = new URL(apiBase);
  } catch {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be an absolute HTTP(S) URL.");
  }
  if (!["http:", "https:"].includes(apiUrl.protocol) || apiUrl.username || apiUrl.password) {
    throw new Error("NEXT_PUBLIC_API_BASE_URL must be an absolute HTTP(S) URL without credentials.");
  }

  if (process.env.VERCEL_ENV === "production") {
    const localHost = ["localhost", "127.0.0.1", "[::1]", "0.0.0.0"].includes(apiUrl.hostname) ||
      apiUrl.hostname.endsWith(".localhost");
    if (apiUrl.protocol !== "https:" || localHost) {
      throw new Error("Production NEXT_PUBLIC_API_BASE_URL must point to the deployed HTTPS API, not localhost.");
    }
  }
}

const nextConfig: NextConfig = {
  /* config options here */
  reactCompiler: true,
  async redirects() {
    return [
      { source: "/sign-in/:path*", destination: "/login/:path*", permanent: false },
      { source: "/sign-up/:path*", destination: "/signup/:path*", permanent: false },
    ];
  },
};

export default function config(phase: string): NextConfig {
  if (phase === PHASE_PRODUCTION_BUILD) validateBuildEnvironment();
  return nextConfig;
}
