/**
 * Battle view types the renderer (battle/plates.ts, GymScene) reads. Lifted from PokeStonks'
 * net/session.ts minus its Colyseus client: in PokéLab a battle is a real training run, so these
 * views are filled from lab events (lab/gymBattle.ts), not a multiplayer room.
 */
import type { SeatKey, StatKey } from 'game-core';

export interface MonView {
  speciesId: string; name: string; affinity: string; level: number;
  hp: number; maxHp: number;
  atk: number; def: number; spa: number; spd: number; spe: number;
  moves: string[];
  pp: Record<string, number>;
  stages: Record<StatKey, number>;
}

export interface PlayerView {
  sessionId: string; wallet: string; ticker: string;
  isBot: boolean; connected: boolean; locked: boolean;
  mon: MonView;
}

export interface Snapshot {
  phase: 'WAITING' | 'INTRO' | 'COMMAND' | 'RESOLVE' | 'END';
  mode: string;
  turnNo: number;
  turnMs: number;
  waitMs: number;
  winner: string;
  moodA: number;
  moodB: number;
  players: Partial<Record<SeatKey, PlayerView>>;
}

