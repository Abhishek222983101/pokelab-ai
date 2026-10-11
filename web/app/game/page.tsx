"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import { LabSocket } from "@/lib/labSocket";
import { useLabStore } from "@/lib/store";

// Phaser needs the DOM/WebGL — never server-rendered.
const PhaserMount = dynamic(() => import("@/game/PhaserMount").then((m) => m.PhaserMount), { ssr: false });

const BACKEND_HOST = process.env.NEXT_PUBLIC_BACKEND_HOST;
const WS_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${BACKEND_HOST ?? window.location.host}/api/ws`
    : "ws://localhost:7700/api/ws";

export default function GamePage() {
  // [BUG FOUND via Playwright]: the game rendered fine but NEVER showed
  // any agents — this page never actually opened a LabSocket at all, so
  // the zustand store it reads from (the same store console/m use) was
  // permanently empty here. Every other page sets this up; this one was
  // missed. Fixed by mounting the same connection pattern.
  const [socket] = useState(() => new LabSocket(WS_URL));
  const setConnectionStatus = useLabStore((s) => s.setConnectionStatus);
  const applyEvent = useLabStore((s) => s.applyEvent);

  useEffect(() => {
    const offStatus = socket.onStatus(setConnectionStatus);
    const offEvent = socket.onEvent(applyEvent);
    socket.connect(0);
    return () => {
      offStatus();
      offEvent();
      socket.close();
    };
  }, [socket, setConnectionStatus, applyEvent]);

  return (
    <main style={{ padding: 16, fontFamily: "monospace" }}>
      <h1>PokéLab</h1>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        Arrow keys to walk. Click the Lab to go inside; click Region to go back out.
      </p>
      <PhaserMount />
    </main>
  );
}
