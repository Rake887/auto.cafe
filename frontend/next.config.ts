import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // Самодостаточная сборка для Docker: .next/standalone с минимальным
  // server.js и только нужными модулями — образ получается лёгким.
  output: "standalone",
  images: {
    remotePatterns: [
      { protocol: "https", hostname: "picsum.photos" },
      { protocol: "https", hostname: "*.picsum.photos" },
    ],
  },
};

export default nextConfig;
