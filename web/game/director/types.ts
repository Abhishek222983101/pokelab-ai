/**
 * §9.5: the Director turns events into animation tasks per entity. The
 * task itself (`run`) is Phaser/DOM code and isn't part of this module —
 * everything here is pure, testable scheduling logic.
 */

export type AnimKind = "walk" | "bubble" | "anim" | "overlay" | "battle_turn" | "sfx";

export interface AnimTask {
  entity: string;
  seq: number;
  kind: AnimKind;
  minMs: number;
  maxMs: number;
  skippable: boolean;
  /** Only used by the real renderer; the Director never calls this —
   * tests exercise scheduling without ever touching Phaser. */
  run?: () => Promise<void>;
  /** Carried through so a compressed/summarized task can still show
   * something meaningful (e.g. bubble text, battle-turn numbers). */
  data?: Record<string, unknown>;
}

export interface CompressedTask extends AnimTask {
  compressed: true;
  originalCount: number;
}
