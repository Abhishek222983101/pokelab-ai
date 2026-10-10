"use client";

import { useEffect, useState } from "react";
import { LabSocket } from "@/lib/labSocket";
import { useLabStore } from "@/lib/store";

const WS_URL =
  typeof window !== "undefined"
    ? `${window.location.protocol === "https:" ? "wss" : "ws"}://${window.location.host}/api/ws`
    : "ws://localhost:7700/api/ws";

export default function ConsolePage() {
  const [socket] = useState(() => new LabSocket(WS_URL));
  const connectionStatus = useLabStore((s) => s.connectionStatus);
  const lastSeq = useLabStore((s) => s.lastSeq);
  const jobs = useLabStore((s) => s.jobs);
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

  const jobList = Object.values(jobs).sort((a, b) => a.jobId.localeCompare(b.jobId));

  return (
    <main style={{ padding: 24, fontFamily: "monospace" }}>
      <header style={{ display: "flex", gap: 16, alignItems: "center", marginBottom: 24 }}>
        <h1 style={{ margin: 0 }}>PokéLab Console</h1>
        <ConnectionBadge status={connectionStatus} />
        <span style={{ opacity: 0.6 }}>last seq: {lastSeq}</span>
      </header>

      <section>
        <h2>Jobs ({jobList.length})</h2>
        {jobList.length === 0 && <p style={{ opacity: 0.6 }}>No jobs yet — submit one through the brain.</p>}
        {jobList.map((job) => (
          <JobPanel key={job.jobId} job={job} />
        ))}
      </section>
    </main>
  );
}

function ConnectionBadge({ status }: { status: "connecting" | "open" | "closed" }) {
  const color = status === "open" ? "#3ecf6a" : status === "connecting" ? "#e0b000" : "#e04040";
  return (
    <span style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 14 }}>
      <span style={{ width: 8, height: 8, borderRadius: 999, background: color, display: "inline-block" }} />
      {status}
    </span>
  );
}

function JobPanel({ job }: { job: ReturnType<typeof useLabStore.getState>["jobs"][string] }) {
  const metricKeys = Object.keys(job.metrics);
  return (
    <div style={{ border: "1px solid #2a2f3a", borderRadius: 8, padding: 12, marginBottom: 12 }}>
      <div style={{ display: "flex", gap: 12, alignItems: "center" }}>
        <strong>{job.jobId}</strong>
        <StatusPill status={job.status} />
        {job.project && <span style={{ opacity: 0.6 }}>project: {job.project}</span>}
      </div>
      {metricKeys.map((key) => {
        const series = job.metrics[key];
        const latest = series[series.length - 1];
        return (
          <div key={key} style={{ fontSize: 13, opacity: 0.85 }}>
            {key}: {latest?.[1]?.toFixed?.(4) ?? latest?.[1]} <span style={{ opacity: 0.5 }}>({series.length} points)</span>
          </div>
        );
      })}
      {job.final && (
        <pre style={{ fontSize: 12, background: "#11141b", padding: 8, borderRadius: 6, marginTop: 8 }}>
          {JSON.stringify(job.final, null, 2)}
        </pre>
      )}
    </div>
  );
}

function StatusPill({ status }: { status: string }) {
  const color = status === "ok" ? "#3ecf6a" : status === "running" ? "#4a9eff" : "#e04040";
  return (
    <span style={{ fontSize: 12, padding: "2px 8px", borderRadius: 999, background: color, color: "#0b0e14" }}>
      {status}
    </span>
  );
}
