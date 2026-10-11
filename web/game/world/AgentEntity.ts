import Phaser from "phaser";

export type AgentRuntimeStatus = "idle" | "working" | "retired";

const STATUS_COLOR: Record<AgentRuntimeStatus, number> = {
  idle: 0x888888,
  working: 0x4a9eff,
  retired: 0x444444,
};

/** One agent on screen (P9.4): a sprite + nameplate + a status ring,
 * exactly the three things §9.4.1 specifies. Always rendered as Eevee
 * (the lore-fixed spawned-specialist species, §2.4) — a real sprite from
 * the asset pipeline, not a placeholder shape. */
export class AgentEntity {
  readonly container: Phaser.GameObjects.Container;
  private readonly ring: Phaser.GameObjects.Arc;
  private readonly nameplate: Phaser.GameObjects.Text;
  private readonly sprite: Phaser.GameObjects.Sprite;

  constructor(scene: Phaser.Scene, x: number, y: number, public readonly agentId: string) {
    this.ring = scene.add.circle(0, 0, 18, 0x888888, 0.3).setStrokeStyle(2, 0x888888);
    this.sprite = scene.add.sprite(0, -4, "mon:eevee:front").setScale(0.8);
    this.nameplate = scene.add.text(0, 20, agentId, {
      fontSize: "10px", color: "#ffffff", backgroundColor: "#00000090",
    }).setOrigin(0.5, 0);

    this.container = scene.add.container(x, y, [this.ring, this.sprite, this.nameplate]);
  }

  setStatus(status: AgentRuntimeStatus): void {
    const color = STATUS_COLOR[status];
    this.ring.setStrokeStyle(2, color);
    this.ring.setFillStyle(color, 0.3);
    this.sprite.setAlpha(status === "retired" ? 0.35 : 1);
    this.nameplate.setAlpha(status === "retired" ? 0.5 : 1);
  }

  setPosition(x: number, y: number): void {
    this.container.setPosition(x, y);
  }

  destroy(): void {
    this.container.destroy();
  }
}
