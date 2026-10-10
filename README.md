# PokéLab

An evolving multi-agent ML research lab (PS03, Elevate 1.0 — DJSCE, 10–11 Oct 2026),
skinned as a Pokémon game. Every animation on screen is caused by a real event in the
log; nothing is faked for the demo.

- Professor Oak is the meta-controller: he spawns, refines, merges and retires agents.
- Agents are Pokémon. A Gym battle is a real training run — our HP is the compute
  budget, the leader's HP is the gap to the paper we're reproducing.
- The Pokédex is memory: findings, failures, lessons.

## Layout

| Dir | What |
|---|---|
| `core/` | Rust: `labd`, the event store, job engine, WebSocket gateway |
| `brain/` | Python: Professor Oak, agents, the LLM router, memory, papers |
| `labml/` | Python: 7 small ML models (Oracle, Navigator, Selector, Medic, Scout, Router, Analysts) |
| `workers/` | Python: GPU worker pool + kits (grokking, distillation, NeRF, materials, arena) |
| `web/` | TypeScript/Next: the game (Phaser) + console, forked from PokeStonks |
| `contracts/` | Single source of truth for event/command types, shared by all three languages |
| `docs/` | `SYSTEM-ARCHITECTURE.md` (full blueprint), `OVERVIEW.md` (plain-language tour) |

## Quickstart

```bash
just init      # .env from example, secrets, deps
just fetch     # sprites, datasets, paper PDFs (needs network once)
just contracts # generate schemas + types, validate fixtures in all 3 languages
just test      # cargo test + pytest + vitest
just up        # build web export, start labd (brings up brain + workers) on :7700
```

See `docs/SYSTEM-ARCHITECTURE.md` for the full design and `docs/PROGRESS.md` for build status.

## Credits

Built on the PokeStonks engine (Phaser 3 + grid-engine), stripped of all web3/blockchain
parts. Pokémon sprites and cries are from public fan asset mirrors (PokeAPI / Showdown /
PMDCollab), used for a local, non-commercial hackathon demo.
