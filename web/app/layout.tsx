import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "PokéLab",
  description: "An evolving AI research lab, played as Pokémon.",
  manifest: "/manifest.json",
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html lang="en">
      <body style={{ margin: 0, fontFamily: "system-ui, sans-serif", background: "#0b0e14", color: "#e6e6e6" }}>
        {children}
      </body>
    </html>
  );
}
