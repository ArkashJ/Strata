import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  async headers() {
    return [
      // Wave 4 / AC4.2 — the embed widget is meant to be iframed anywhere; relax
      // the frame policy on that path only (the rest of the app stays default).
      {
        source: "/embed/:path*",
        headers: [
          { key: "X-Frame-Options", value: "ALLOWALL" },
          { key: "Content-Security-Policy", value: "frame-ancestors *" },
        ],
      },
    ];
  },
};

export default nextConfig;
