import Phaser from "phaser";
import { Direction, createGridWorld, TILE_SIZE, GRID_WIDTH, GRID_HEIGHT, BUILDINGS } from "../world/gridWorld";
import type { GridEngineHeadless } from "grid-engine";
import { mountBindingOverlay } from "../world/bindingOverlay";

/** The region map (P9.2): Ash walks a real grid-engine-driven grid
 * between four buildings. No Tiled tileset — ground is a flat-color
 * texture generated at runtime (see create()), buildings are labelled
 * rectangles. Walking onto the Lab warps to the interior (P9.3). */
export class RegionScene extends Phaser.Scene {
  private world!: GridEngineHeadless;
  private ashSprite!: Phaser.GameObjects.Sprite;
  private cursors!: Phaser.Types.Input.Keyboard.CursorKeys;
  private lastMoveAt = 0;

  constructor() {
    super("region");
  }

  create() {
    // a flat ground tile generated on the fly — no external tile asset needed
    const g = this.add.graphics();
    g.fillStyle(0x2a3f2a, 1);
    g.fillRect(0, 0, TILE_SIZE, TILE_SIZE);
    g.lineStyle(1, 0x1f301f, 1);
    g.strokeRect(0, 0, TILE_SIZE, TILE_SIZE);
    g.generateTexture("ground-tile", TILE_SIZE, TILE_SIZE);
    g.destroy();

    for (let y = 0; y < GRID_HEIGHT; y++) {
      for (let x = 0; x < GRID_WIDTH; x++) {
        this.add.image(x * TILE_SIZE, y * TILE_SIZE, "ground-tile").setOrigin(0);
      }
    }

    for (const b of BUILDINGS) {
      const rect = this.add.rectangle(
        b.x * TILE_SIZE, b.y * TILE_SIZE, b.w * TILE_SIZE, b.h * TILE_SIZE, Phaser.Display.Color.HexStringToColor(b.color).color
      ).setOrigin(0).setStrokeStyle(2, 0xffffff, 0.6);
      const warpTargets: Record<string, string> = { lab: "lab", gym: "gym" };
      const warpTo = warpTargets[b.id];
      rect.setInteractive({ useHandCursor: !!warpTo });
      if (warpTo) {
        rect.on("pointerdown", () => this.scene.start(warpTo));
      }
      this.add.text(b.x * TILE_SIZE + 4, b.y * TILE_SIZE + 4, b.label, {
        fontSize: "12px", color: "#ffffff", backgroundColor: "#00000080",
      });
    }

    this.world = createGridWorld([{ id: "ash", x: 1, y: 1 }]);
    this.ashSprite = this.add.sprite(TILE_SIZE, TILE_SIZE, "trainer:ash").setOrigin(0.5, 1);
    this.syncAshSpritePosition();

    this.cursors = this.input.keyboard!.createCursorKeys();

    this.add.text(4, GRID_HEIGHT * TILE_SIZE + 4, "Arrow keys to walk. Click the Lab to go inside.", {
      fontSize: "11px", color: "#aaaaaa",
    });

    mountBindingOverlay(this);
  }

  update(_time: number, delta: number) {
    this.world.update(delta, delta);
    this.syncAshSpritePosition();

    if (this.time.now - this.lastMoveAt < 120) return; // simple input throttle, tile-by-tile feel
    let dir: Direction | null = null;
    if (this.cursors.left.isDown) dir = Direction.LEFT;
    else if (this.cursors.right.isDown) dir = Direction.RIGHT;
    else if (this.cursors.up.isDown) dir = Direction.UP;
    else if (this.cursors.down.isDown) dir = Direction.DOWN;
    if (dir !== null) {
      this.world.move("ash", dir);
      this.lastMoveAt = this.time.now;
    }
  }

  private syncAshSpritePosition() {
    const pos = this.world.getPosition("ash");
    this.ashSprite.setPosition((pos.x + 0.5) * TILE_SIZE, (pos.y + 1) * TILE_SIZE);
  }
}
