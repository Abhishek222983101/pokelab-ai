import Phaser from "phaser";
import { useLabStore } from "@/lib/store";

/**
 * P9.8's binding proof: Shift+E toggles a HUD showing the real event
 * seq this screen is caught up to, live from the same store every
 * other visual in the game reads from. If this number isn't moving,
 * nothing on screen is either — there's no other path to "truth" here
 * to fake.
 */
export function mountBindingOverlay(scene: Phaser.Scene): void {
  const text = scene.add.text(scene.scale.width - 8, 8, "", {
    fontSize: "11px", color: "#3ecf6a", backgroundColor: "#000000a0", padding: { x: 4, y: 2 },
  }).setOrigin(1, 0).setVisible(false).setDepth(1000);

  const update = () => {
    const state = useLabStore.getState();
    text.setText(`seq: ${state.lastSeq} · ${Object.keys(state.agents).length} agents · ${Object.keys(state.jobs).length} jobs`);
  };
  update();
  const unsubscribe = useLabStore.subscribe(update);

  const keyHandler = (event: KeyboardEvent) => {
    if (event.shiftKey && event.key.toLowerCase() === "e") {
      text.setVisible(!text.visible);
    }
  };
  scene.input.keyboard?.on("keydown", keyHandler);

  scene.events.once(Phaser.Scenes.Events.SHUTDOWN, () => {
    unsubscribe();
    scene.input.keyboard?.off("keydown", keyHandler);
  });
}
