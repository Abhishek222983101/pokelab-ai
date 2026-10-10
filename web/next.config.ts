import type { NextConfig } from "next";

// Static export: labd serves the built app from web/out/ (§4.4, §8.2) —
// there is no Next.js server in production, which is what lets labd be
// the single process a demo has to keep alive.
const nextConfig: NextConfig = {
  output: "export",
  images: { unoptimized: true },
  // Without this, `/console` exports as console.html + an empty console/
  // dir, and a plain static file server (tower-http's ServeDir on the
  // Rust side) redirects /console -> /console/ then 404s (no index
  // there). trailingSlash makes every route export as <route>/index.html,
  // which IS what a directory listing expects. [BUG FOUND via a real
  // curl against labd, not assumed — see docs/PROGRESS.md P8.2]
  trailingSlash: true,
};

export default nextConfig;
