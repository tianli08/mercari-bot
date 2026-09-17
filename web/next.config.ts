import type { NextConfig } from "next";

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

export default nextConfig;
