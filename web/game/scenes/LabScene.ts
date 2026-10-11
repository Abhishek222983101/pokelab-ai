import Phaser from "phaser";
import { useLabStore } from "@/lib/store";
import { AgentEntity, AgentRuntimeStatus } from "../world/AgentEntity";
import { Station, stationFor } from "../world/stations";
import { sfxRetire, sfxSpawn } from "../world/audio";
import { mountBindingOverlay } from "../world/bindingOverlay";

const STATION_POSITIONS: Record<Station, { x: number; y: number }> = {
  library_desk: { x: 80, y: 80 },
  code_bench: { x: 240, y: 80 },
  server_rack: { x: 400, y: 80 },
  pokemon_center: { x: 80, y: 220 },
  quest_board: { x: 240, y: 220 },
  arena_door: { x: 400, y: 220 },
  analysis_table: { x: 80, y: 360 },
  scribe_desk: { x: 240, y: 360 },
};

/** The Lab interior (P9.3): Oak's stations, and every active/retired
 * agent standing at the station its FIRST matching capability maps to
 * (§9.4.2, stations.ts — already real and tested). Driven live by the
 * real zustand store, which is itself folded purely from real events —
 * no entity here exists that doesn't trace back to an agent.* event. */
export class LabScene extends Phaser.Scene {
  private entities = new Map<string, AgentEntity>();
  private unsubscribe: (() => void) | null = null;
  private stationOffsets = new Map<Station, number>();
  private knownStatuses = new Map<string, AgentRuntimeStatus>();

  constructor() {
    super("lab");
  }

  create() {
    for (const [stationId, pos] of Object.entries(STATION_POSITIONS)) {
      this.add.rectangle(pos.x, pos.y, 64, 40, 0x3a3f4a).setStrokeStyle(1, 0x5a5f6a);
      this.add.text(pos.x, pos.y - 30, stationId.replace("_", " "), {
        fontSize: "9px", color: "#888",
      }).setOrigin(0.5);
    }

    const exitButton = this.add.text(8, 8, "< Region", { fontSize: "12px", backgroundColor: "#222", padding: { x: 6, y: 4 } })
      .setInteractive({ useHandCursor: true });
    exitButton.on("pointerdown", () => this.scene.start("region"));

    this.syncFromStore(useLabStore.getState());
    this.unsubscribe = useLabStore.subscribe((state) => this.syncFromStore(state));

    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.unsubscribe?.());

    mountBindingOverlay(this);
  }

  private syncFromStore(state: ReturnType<typeof useLabStore.getState>) {
    const seen = new Set<string>();
    const stationCounts = new Map<Station, number>();

    for (const agent of Object.values(state.agents)) {
      seen.add(agent.agentId);
      const station = stationFor(agent.capabilities) ?? "analysis_table";
      const base = STATION_POSITIONS[station];
      const slot = stationCounts.get(station) ?? 0;
      stationCounts.set(station, slot + 1);
      const x = base.x + (slot % 3) * 20 - 20;
      const y = base.y + Math.floor(slot / 3) * 20;

      let entity = this.entities.get(agent.agentId);
      const isNewEntity = !entity;
      if (!entity) {
        entity = new AgentEntity(this, x, y, agent.agentId);
        this.entities.set(agent.agentId, entity);
      } else {
        entity.setPosition(x, y);
      }

      const hasRunningJob = Object.values(state.jobs).some((j) => j.status === "running");
      const status: AgentRuntimeStatus = agent.status === "retired" ? "retired" : hasRunningJob ? "working" : "idle";
      entity.setStatus(status);

      // §9.7: a real overlay + sfx the FIRST time we see this agent exist
      // (spawn) or flip to retired — driven by the real event-folded
      // store, not a separate animation script.
      const previousStatus = this.knownStatuses.get(agent.agentId);
      if (isNewEntity) {
        this.playSpawnFlash(entity);
        sfxSpawn();
      } else if (previousStatus !== "retired" && status === "retired") {
        this.playRetireFade(entity);
        sfxRetire();
      }
      this.knownStatuses.set(agent.agentId, status);
    }

    for (const [id, entity] of this.entities) {
      if (!seen.has(id)) {
        entity.destroy();
        this.entities.delete(id);
      }
    }
  }

  /** The classic white-flash-in overlay (§9.3's Overlays table), scaled
   * down to a per-entity flash rather than a full-screen one — multiple
   * agents can spawn close together without fighting over one global
   * overlay slot. */
  private playSpawnFlash(entity: AgentEntity) {
    entity.container.setAlpha(0);
    entity.container.setScale(0.3);
    this.tweens.add({
      targets: entity.container,
      alpha: 1, scale: 1,
      duration: 500, ease: "Back.Out",
    });
  }

  private playRetireFade(entity: AgentEntity) {
    this.tweens.add({
      targets: entity.container,
      alpha: 0.4, y: entity.container.y + 6,
      duration: 600, ease: "Sine.In",
    });
  }
}
