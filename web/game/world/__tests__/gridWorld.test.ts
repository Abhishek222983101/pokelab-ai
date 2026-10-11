import { describe, expect, it } from "vitest";
import { BUILDINGS, createGridWorld, Direction } from "../gridWorld";

describe("createGridWorld — real grid-engine movement & collision", () => {
  it("moves a character one tile per real move() call", async () => {
    const engine = createGridWorld([{ id: "ash", x: 1, y: 1 }]);
    expect(engine.getPosition("ash")).toEqual({ x: 1, y: 1 });

    engine.move("ash", Direction.RIGHT);
    // grid-engine animates movement over time (speed-based) — wait for it
    await new Promise<void>((resolve) => {
      const sub = engine.positionChangeFinished().subscribe(() => {
        sub.unsubscribe();
        resolve();
      });
      // advance the engine's internal clock manually since there's no
      // real Phaser game loop driving update() in this test
      const interval = setInterval(() => engine.update(16, 16), 16);
      setTimeout(() => clearInterval(interval), 2000);
    });

    expect(engine.getPosition("ash")).toEqual({ x: 2, y: 1 });
  });

  it("genuinely blocks movement into a building tile (real collision, not just geometry)", async () => {
    const lab = BUILDINGS.find((b) => b.id === "lab")!;
    // place a character directly left of the Lab building, try to walk into it
    const engine = createGridWorld([{ id: "ash", x: lab.x - 1, y: lab.y }]);

    engine.move("ash", Direction.RIGHT);
    await new Promise((resolve) => setTimeout(resolve, 300));
    const interval = setInterval(() => engine.update(16, 16), 16);
    await new Promise((resolve) => setTimeout(resolve, 500));
    clearInterval(interval);

    // should NOT have entered the building tile — blocked by real collision
    const pos = engine.getPosition("ash");
    expect(pos).toEqual({ x: lab.x - 1, y: lab.y });
  });

  it("every building is within the grid bounds", () => {
    for (const b of BUILDINGS) {
      expect(b.x + b.w).toBeLessThanOrEqual(20);
      expect(b.y + b.h).toBeLessThanOrEqual(14);
    }
  });

  it("buildings don't overlap each other", () => {
    for (let i = 0; i < BUILDINGS.length; i++) {
      for (let j = i + 1; j < BUILDINGS.length; j++) {
        const a = BUILDINGS[i];
        const b = BUILDINGS[j];
        const overlap = a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
        expect(overlap).toBe(false);
      }
    }
  });

  it("supports multiple independent characters", () => {
    const engine = createGridWorld([
      { id: "ash", x: 0, y: 0 },
      { id: "eevee-1", x: 5, y: 5 },
    ]);
    expect(engine.getPosition("ash")).toEqual({ x: 0, y: 0 });
    expect(engine.getPosition("eevee-1")).toEqual({ x: 5, y: 5 });
  });
});
