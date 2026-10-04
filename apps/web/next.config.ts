import type { NextConfig } from "next";

const apiOrigin = process.env.API_ORIGIN || "http://localhost:8000";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  async rewrites() {
    // Browser never calls the backend directly — same-origin proxy.
    return [
      { source: "/api/:path*", destination: `${apiOrigin}/api/:path*` },
      { source: "/ws/:path*", destination: `${apiOrigin}/ws/:path*` },
    ];
  },
};

export default nextConfig;
