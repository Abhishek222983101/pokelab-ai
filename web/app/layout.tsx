import type { Metadata, Viewport } from "next";
import "@fontsource/atkinson-hyperlegible-next/400.css";
import "@fontsource/atkinson-hyperlegible-next/700.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "PokéLab — Professor Oak's Evolving Research Lab",
  description: "An evolving AI research lab you can watch, play and steer like a Pokémon game.",
  manifest: "/manifest.json",
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#183088",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en" style={{ ["--font-atkinson" as string]: '"Atkinson Hyperlegible Next"' }}>
      <body>{children}</body>
    </html>
  );
}
