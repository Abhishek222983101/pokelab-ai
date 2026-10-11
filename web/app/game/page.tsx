"use client";

import dynamic from "next/dynamic";
import { useLabConnection } from "@/lib/useLabConnection";

// Phaser needs the DOM/WebGL — never server-rendered.
const PhaserMount = dynamic(() => import("@/game/PhaserMount"), { ssr: false });

export default function GamePage() {
  useLabConnection();
  return (
    <main className="fixed inset-0 overflow-hidden bg-navy-deep">
      <PhaserMount marketId="aapl" speciesId="aapl" wallet="" onExit={() => {}} />
    </main>
  );
}
