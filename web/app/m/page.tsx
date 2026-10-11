"use client";

import { useEffect, useState } from "react";
import { LabSocket } from "@/lib/labSocket";
import { useLabStore } from "@/lib/store";

const TOKEN_STORAGE_KEY = "pokelab_phone_token";

const BACKEND_HOST = process.env.NEXT_PUBLIC_BACKEND_HOST;
const WS_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${BACKEND_HOST ?? window.location.host}/api/ws`
    : "ws://localhost:7700/api/ws";

function apiUrl(path: string): string {
  if (typeof window === "undefined") return path;
  return `${window.location.protocol}//${BACKEND_HOST ?? window.location.host}${path}`;
}

export default function PokegearPage() {
  const [token, setToken] = useState<string | null>(null);
  const [role, setRole] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [pairError, setPairError] = useState<string | null>(null);
  const [socket, setSocket] = useState<LabSocket | null>(null);

  const connectionStatus = useLabStore((s) => s.connectionStatus);
  const jobs = useLabStore((s) => s.jobs);
  const setConnectionStatus = useLabStore((s) => s.setConnectionStatus);
  const applyEvent = useLabStore((s) => s.applyEvent);
  const [lastCommandResult, setLastCommandResult] = useState<string | null>(null);

  // try to restore a saved pairing on load — browser storage per §
  // artifact-capabilities guidance: per-device convenience only, never
  // the source of truth (the token itself IS the source of truth; this
  // just avoids re-pairing every page load on the SAME phone)
  useEffect(() => {
    try {
      const saved = localStorage.getItem(TOKEN_STORAGE_KEY);
      if (saved) {
        const parsed = JSON.parse(saved);
        setToken(parsed.token);
        setRole(parsed.role);
      }
    } catch {
      // private browsing / blocked storage — just start unpaired, no crash
    }
  }, []);

  useEffect(() => {
    if (!token) return;
    const s = new LabSocket(WS_URL);
    setSocket(s);
    const offStatus = s.onStatus(setConnectionStatus);
    const offEvent = s.onEvent(applyEvent);
    const offCommand = s.onCommandResult((r) => setLastCommandResult(`${r.command}: ${r.ok ? "ok" : "failed"} — ${r.detail}`));
    s.connect(0);
    return () => {
      offStatus();
      offEvent();
      offCommand();
      s.close();
    };
  }, [token, setConnectionStatus, applyEvent]);

  async function claimCode() {
    setPairError(null);
    try {
      const deviceId = `phone-${Math.random().toString(36).slice(2, 10)}`;
      const resp = await fetch(apiUrl("/api/pair/claim"), {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ code: code.trim().toUpperCase(), device_id: deviceId }),
      });
      if (!resp.ok) {
        setPairError(resp.status === 401 ? "code invalid, used, or expired" : `pairing failed (${resp.status})`);
        return;
      }
      const data = await resp.json();
      setToken(data.token);
      setRole(data.role);
      try {
        localStorage.setItem(TOKEN_STORAGE_KEY, JSON.stringify({ token: data.token, role: data.role }));
      } catch {
        // storage blocked — pairing still works for this session, just won't persist
      }
    } catch {
      setPairError("could not reach the lab — check you're on the same network / tunnel");
    }
  }

  function unpair() {
    socket?.close();
    setSocket(null);
    setToken(null);
    setRole(null);
    try {
      localStorage.removeItem(TOKEN_STORAGE_KEY);
    } catch {
      // ignore
    }
  }

  if (!token) {
    return (
      <main style={{ padding: 16, fontFamily: "monospace", maxWidth: 420 }}>
        <h1>Pokégear</h1>
        <p>Enter the 6-character code shown on the desk console to pair.</p>
        <input
          value={code}
          onChange={(e) => setCode(e.target.value)}
          placeholder="ABC123"
          maxLength={6}
          style={{ fontSize: 24, letterSpacing: 4, textTransform: "uppercase", width: "100%", padding: 8 }}
        />
        <button onClick={claimCode} style={{ marginTop: 12, padding: "8px 16px" }}>
          Pair
        </button>
        {pairError && <p style={{ color: "#e04040" }}>{pairError}</p>}
      </main>
    );
  }

  const jobList = Object.values(jobs).sort((a, b) => a.jobId.localeCompare(b.jobId));

  return (
    <main style={{ padding: 16, fontFamily: "monospace" }}>
      <header style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
        <h1 style={{ margin: 0, fontSize: 20 }}>Pokégear</h1>
        <button onClick={unpair} style={{ fontSize: 12 }}>unpair</button>
      </header>
      <p style={{ fontSize: 13, opacity: 0.7 }}>
        role: {role} · connection: {connectionStatus}
      </p>
      {lastCommandResult && <p style={{ fontSize: 12, color: "#e0b000" }}>{lastCommandResult}</p>}

      <h2 style={{ fontSize: 16 }}>Jobs</h2>
      {jobList.length === 0 && <p style={{ opacity: 0.6 }}>No jobs running.</p>}
      {jobList.map((job) => (
        <div key={job.jobId} style={{ border: "1px solid #2a2f3a", borderRadius: 8, padding: 10, marginBottom: 8 }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
            <span>
              <strong>{job.jobId}</strong> — {job.status}
            </span>
            {job.status === "running" && (
              <button onClick={() => socket?.sendCommand("kill_job", job.jobId)} style={{ fontSize: 12, color: "#e04040" }}>
                kill
              </button>
            )}
          </div>
        </div>
      ))}
    </main>
  );
}
