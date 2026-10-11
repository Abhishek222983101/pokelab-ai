import Phaser from "phaser";
import { useLabStore } from "@/lib/store";
import { sfxReproduced } from "../world/audio";
import { mountBindingOverlay } from "../world/bindingOverlay";
import { GYM_LEADERS, GymLeader } from "../world/gymLeaders";

const BADGE_STORAGE_KEY = "pokelab.badges";

function loadBadges(): Set<string> {
  try {
    const raw = localStorage.getItem(BADGE_STORAGE_KEY);
    return raw ? new Set(JSON.parse(raw)) : new Set();
  } catch {
    return new Set(); // private-mode/blocked storage: badges just won't persist, nothing else breaks
  }
}

function saveBadge(kit: string): void {
  try {
    const badges = loadBadges();
    badges.add(kit);
    localStorage.setItem(BADGE_STORAGE_KEY, JSON.stringify([...badges]));
  } catch {
    /* best-effort cosmetic persistence only */
  }
}

/** The Gym (P9.6/P11.6 "four-gym run"): a leader-select room with one
 * real boss per paper kit (gymLeaders.ts), each leader's HP bar driven
 * live by that kit's own real job metric against its own real curated
 * claim — not one hardcoded grokking battle reused with different
 * labels. Picking a leader with no matching real job yet just shows
 * "waiting for a run" — there is no synthetic/pre-scripted fallback. */
export class GymScene extends Phaser.Scene {
  private mode: "select" | "battle" = "select";
  private selectedLeader: GymLeader | null = null;
  private leaderHpBar!: Phaser.GameObjects.Rectangle;
  private ourHpBar!: Phaser.GameObjects.Rectangle;
  private logText!: Phaser.GameObjects.Text;
  private unsubscribe: (() => void) | null = null;
  private trackedJobId: string | null = null;
  private reproducedAnnounced = new Set<string>();
  private container!: Phaser.GameObjects.Container;

  constructor() {
    super("gym");
  }

  create() {
    this.add.text(8, 8, "< Region", { fontSize: "12px", backgroundColor: "#222", padding: { x: 6, y: 4 } })
      .setInteractive({ useHandCursor: true })
      .on("pointerdown", () => this.scene.start("region"));

    this.container = this.add.container(0, 0);
    this.showLeaderSelect();

    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.unsubscribe?.());

    mountBindingOverlay(this);
  }

  private clearContainer() {
    this.container.removeAll(true);
    this.unsubscribe?.();
    this.unsubscribe = null;
  }

  private showLeaderSelect() {
    this.mode = "select";
    this.clearContainer();
    const badges = loadBadges();

    this.container.add(this.add.text(260, 24, "Choose a Gym Leader", { fontSize: "15px" }).setOrigin(0.5));
    GYM_LEADERS.forEach((leader, i) => {
      const y = 60 + i * 44;
      const earned = badges.has(leader.kit);
      const row = this.add.text(40, y, `${earned ? "★" : "☆"} ${leader.name}`, {
        fontSize: "13px", backgroundColor: "#333", padding: { x: 8, y: 6 },
      }).setInteractive({ useHandCursor: true });
      row.on("pointerdown", () => this.showBattle(leader));
      const sub = this.add.text(40, y + 20, leader.paperTitle, { fontSize: "10px", color: "#999" });
      this.container.add([row, sub]);
    });
  }

  private showBattle(leader: GymLeader) {
    this.mode = "battle";
    this.selectedLeader = leader;
    this.trackedJobId = null;
    this.clearContainer();

    const back = this.add.text(380, 8, "< Leaders", { fontSize: "11px", backgroundColor: "#222", padding: { x: 6, y: 4 } })
      .setInteractive({ useHandCursor: true });
    back.on("pointerdown", () => this.showLeaderSelect());

    this.container.add(this.add.text(260, 30, leader.name, { fontSize: "13px" }).setOrigin(0.5));
    this.container.add(this.add.rectangle(260, 50, 200, 14, 0x333333).setStrokeStyle(1, 0xffffff));
    this.leaderHpBar = this.add.rectangle(161, 50, 198, 12, 0xe04040).setOrigin(0, 0.5);

    this.container.add(this.add.text(260, 90, "Our run", { fontSize: "13px" }).setOrigin(0.5));
    this.container.add(this.add.rectangle(260, 110, 200, 14, 0x333333).setStrokeStyle(1, 0xffffff));
    this.ourHpBar = this.add.rectangle(161, 110, 198, 12, 0x3ecf6a).setOrigin(0, 0.5);

    this.logText = this.add.text(20, 150, "waiting for a run...", { fontSize: "12px", color: "#ccc", wordWrap: { width: 480 } });
    this.container.add([back, this.leaderHpBar, this.ourHpBar, this.logText]);

    this.syncFromStore(useLabStore.getState());
    this.unsubscribe = useLabStore.subscribe((state) => this.syncFromStore(state));
  }

  private syncFromStore(state: ReturnType<typeof useLabStore.getState>) {
    if (this.mode !== "battle" || !this.selectedLeader) return;
    const leader = this.selectedLeader;
    const jobs = Object.values(state.jobs).filter((j) => j.kit === leader.kit);
    const job = this.trackedJobId
      ? state.jobs[this.trackedJobId] ?? jobs[jobs.length - 1]
      : jobs.find((j) => j.metrics[leader.metricKey]) ?? jobs[jobs.length - 1];
    if (!job) {
      this.logText.setText(`waiting for a real ${leader.kit} run...`);
      return;
    }
    this.trackedJobId = job.jobId;

    const series = job.metrics[leader.metricKey];
    const latest = series?.[series.length - 1]?.[1] ?? 0;
    const gapFraction = Math.max(0, Math.min(1, (leader.targetValue - latest) / leader.targetValue));
    this.leaderHpBar.width = 198 * gapFraction;

    const stepsSeries = Object.values(job.metrics)[0];
    const progressFraction = job.status === "running" ? Math.min(1, (stepsSeries?.length ?? 0) / 30) : 1;
    this.ourHpBar.width = 198 * progressFraction;

    const lines = [`job: ${job.jobId} (${job.status})`];
    if (series) lines.push(`${leader.metricKey}: ${latest.toFixed(3)} (target ${leader.targetValue})`);
    const reproduced = job.status === "ok" && latest >= leader.targetValue;
    if (reproduced) {
      lines.push(`Reproduced! ${leader.name.split(" (")[0]}'s Pokémon fainted. Badge earned.`);
      if (!this.reproducedAnnounced.has(job.jobId)) {
        this.reproducedAnnounced.add(job.jobId);
        sfxReproduced();
        saveBadge(leader.kit);
      }
    }
    this.logText.setText(lines.join("\n"));
  }
}
