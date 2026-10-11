/**
 * The shared lab store (console, phone and game all read it). State changes ONLY by folding an event
 * through the pure reducer in labReducer.ts — never a direct setter from a click or a scene.
 */
import { create } from "zustand";
import type { LabEvent } from "./labSocket";
import { recordEventLatency } from "./perf";
import { emptyLabView, reduce, type LabView } from "./labReducer";

export type { JobViewState, AgentViewState, ProjectViewState, PlanStepView, CurrentTask, LabView } from "./labReducer";
export { levelOf, MAX_RECENT_EVENTS } from "./labReducer";

interface LabStoreState extends LabView {
  connectionStatus: "connecting" | "open" | "closed";
  setConnectionStatus: (s: "connecting" | "open" | "closed") => void;
  applyEvent: (e: LabEvent) => void;
}

export const useLabStore = create<LabStoreState>((set) => ({
  connectionStatus: "connecting",
  ...emptyLabView(),

  setConnectionStatus: (s) => set({ connectionStatus: s }),

  applyEvent: (e) => {
    recordEventLatency(e.ts);
    set((state) => reduce(state, e));
  },
}));
