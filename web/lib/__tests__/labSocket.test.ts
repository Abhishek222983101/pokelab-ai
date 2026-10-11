import { describe, expect, it, vi, beforeEach } from "vitest";
import { LabSocket } from "../labSocket";

class FakeWebSocket {
  static OPEN = 1;
  static instances: FakeWebSocket[] = [];
  readyState = FakeWebSocket.OPEN;
  onopen: (() => void) | null = null;
  onmessage: ((ev: { data: string }) => void) | null = null;
  onclose: (() => void) | null = null;
  onerror: (() => void) | null = null;
  sent: string[] = [];

  constructor(public url: string) {
    FakeWebSocket.instances.push(this);
    setTimeout(() => this.onopen?.(), 0);
  }

  send(data: string) {
    this.sent.push(data);
  }

  close() {
    this.onclose?.();
  }

  // test helper: simulate the server pushing a message
  receive(obj: unknown) {
    this.onmessage?.({ data: JSON.stringify(obj) });
  }
}

beforeEach(() => {
  FakeWebSocket.instances = [];
  // @ts-expect-error - test substitute for the browser global
  globalThis.WebSocket = FakeWebSocket;
});

describe("LabSocket.sendCommand / onCommandResult", () => {
  it("sends a well-formed command message once open", async () => {
    const socket = new LabSocket("ws://test");
    socket.connect(0);
    await new Promise((r) => setTimeout(r, 0));

    socket.sendCommand("kill_job", "job-1");

    const ws = FakeWebSocket.instances[0];
    const sent = JSON.parse(ws.sent[ws.sent.length - 1]);
    expect(sent).toEqual({ type: "command", command: "kill_job", job_id: "job-1" });
  });

  it("does not send while not connected (no throw)", () => {
    const socket = new LabSocket("ws://test");
    expect(() => socket.sendCommand("kill_job", "job-1")).not.toThrow();
  });

  it("delivers command_result to registered handlers", async () => {
    const socket = new LabSocket("ws://test");
    const results: unknown[] = [];
    socket.onCommandResult((r) => results.push(r));
    socket.connect(0);
    await new Promise((r) => setTimeout(r, 0));

    const ws = FakeWebSocket.instances[0];
    ws.receive({ type: "command_result", command: "kill_job", ok: true, detail: "stop sent for job-1" });

    expect(results).toEqual([{ command: "kill_job", ok: true, detail: "stop sent for job-1" }]);
  });
});
