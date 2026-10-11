"use client";

import { useEffect, useState } from "react";
import { LabSocket } from "./labSocket";
import { useLabStore } from "./store";

/** Same-origin under `labd up`; a static deploy (no labd behind it) points this at the real host. */
export const BACKEND_HOST = process.env.NEXT_PUBLIC_BACKEND_HOST;

export function labWsUrl(): string {
  if (typeof window === "undefined") return "ws://localhost:7700/api/ws";
  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  return `${scheme}://${BACKEND_HOST ?? window.location.host}/api/ws`;
}

export function labApiUrl(path: string): string {
  if (typeof window === "undefined") return path;
  return `${window.location.protocol}//${BACKEND_HOST ?? window.location.host}${path}`;
}

/** One live connection per page, folding every event into the shared store from seq 0. */
export function useLabConnection(): LabSocket {
  const [socket] = useState(() => new LabSocket(labWsUrl()));
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

  return socket;
}
