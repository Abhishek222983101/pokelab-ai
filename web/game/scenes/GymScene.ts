import Phaser from "phaser";
import { useLabStore } from "@/lib/store";
import { sfxReproduced } from "../world/audio";
import { mountBindingOverlay } from "../world/bindingOverlay";

const TARGET_METRIC_KEY = "test_acc";
const TARGET_VALUE = 0.95; // the grokking PaperPack's curated claim (packs.py) — kept in sync by hand

/** The Gym (P9.6): a real job's test_acc, read live from the store, IS
 * the leader's HP — no synthetic animation, no pre-scripted sequence.
 * Our HP is simple elapsed-steps-vs-total. Turn-by-turn narration is
 * simplified to "show the latest real checkpoint," not full batched
 * turn synthesis (§9.5's fuller version) — an honest scope cut, not
 * claimed as done. */
export class GymScene extends Phaser.Scene {
  private leaderHpBar!: Phaser.GameObjects.Rectangle;
  private ourHpBar!: Phaser.GameObjects.Rectangle;
  private logText!: Phaser.GameObjects.Text;
  private unsubscribe: (() => void) | null = null;
  private trackedJobId: string | null = null;
  private reproducedAnnounced = new Set<string>();

  constructor() {
    super("gym");
  }

  create() {
    this.add.text(8, 8, "< Region", { fontSize: "12px", backgroundColor: "#222", padding: { x: 6, y: 4 } })
      .setInteractive({ useHandCursor: true })
      .on("pointerdown", () => this.scene.start("region"));

    this.add.text(260, 30, "Gym Leader (the paper)", { fontSize: "13px" }).setOrigin(0.5);
    this.add.rectangle(260, 50, 200, 14, 0x333333).setStrokeStyle(1, 0xffffff);
    this.leaderHpBar = this.add.rectangle(161, 50, 198, 12, 0xe04040).setOrigin(0, 0.5);

    this.add.text(260, 90, "Our run", { fontSize: "13px" }).setOrigin(0.5);
    this.add.rectangle(260, 110, 200, 14, 0x333333).setStrokeStyle(1, 0xffffff);
    this.ourHpBar = this.add.rectangle(161, 110, 198, 12, 0x3ecf6a).setOrigin(0, 0.5);

    this.logText = this.add.text(20, 150, "waiting for a run...", { fontSize: "12px", color: "#ccc", wordWrap: { width: 480 } });

    this.syncFromStore(useLabStore.getState());
    this.unsubscribe = useLabStore.subscribe((state) => this.syncFromStore(state));
    this.events.once(Phaser.Scenes.Events.SHUTDOWN, () => this.unsubscribe?.());

    mountBindingOverlay(this);
  }

  private syncFromStore(state: ReturnType<typeof useLabStore.getState>) {
    const jobs = Object.values(state.jobs);
    const job = this.trackedJobId
      ? state.jobs[this.trackedJobId] ?? jobs[jobs.length - 1]
      : jobs.find((j) => j.metrics[TARGET_METRIC_KEY]) ?? jobs[jobs.length - 1];
    if (!job) return;
    this.trackedJobId = job.jobId;

    const series = job.metrics[TARGET_METRIC_KEY];
    const latest = series?.[series.length - 1]?.[1] ?? 0;
    const gapFraction = Math.max(0, Math.min(1, (TARGET_VALUE - latest) / TARGET_VALUE));
    this.leaderHpBar.width = 198 * gapFraction;

    const stepsSeries = Object.values(job.metrics)[0];
    const progressFraction = job.status === "running" ? Math.min(1, (stepsSeries?.length ?? 0) / 30) : 1;
    this.ourHpBar.width = 198 * progressFraction;

    const lines = [`job: ${job.jobId} (${job.status})`];
    if (series) lines.push(`${TARGET_METRIC_KEY}: ${(latest * 100).toFixed(1)}% (target ${(TARGET_VALUE * 100).toFixed(0)}%)`);
    const reproduced = job.status === "ok" && latest >= TARGET_VALUE;
    if (reproduced) {
      lines.push("Reproduced! The leader's Pokémon fainted.");
      if (!this.reproducedAnnounced.has(job.jobId)) {
        this.reproducedAnnounced.add(job.jobId);
        sfxReproduced();
      }
    }
    this.logText.setText(lines.join("\n"));
  }
}
