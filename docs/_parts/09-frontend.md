# PART 9 — THE GAME, THE CONSOLE & THE PHONE

## 9.1 The web app

- **Fork** `~/PokeStonks/apps/web` → `~/elevate-ps03/web` (copy, fresh history); bump `next`/`eslint-config-next` to **16.3.8** (security); keep `phaser` 3.80.1 + `grid-engine` 2.45.0 exactly (§4.3.3). Keep: `game/art/*`, `game/audio/*`, `game/overworld/{controls,dialog,hud,ui,mapTypes,maps,cutscene}.ts`, `game/battle/{dialog,fx,plates,menu,ui,turns}.ts`, `game/scenes/{BootScene,PreloadScene}.ts`, `PhaserMount.tsx`, fonts, `globals.css`. Delete: `web3/`, `components/{Globe,MarketPins,MarketSheet,ClaimLayer,ConnectWalletDialog,NftCard,PixelBlast,BrokerSelect,DuelDialog}`, `collection/`, `api/spawns`, `stores/walletStore`, `game/net/session.ts` (Colyseus), `game/flow/*`, the `game-core`/`contracts-abi` workspace deps.
- **Static export** (`next.config.ts`: `output: 'export'`, `images.unoptimized: true`, `trailingSlash: true`) → `web/out/` served by labd. Routes: `/` (desk: game + console), `/m/` (phone), `/replay/` (replay picker). ⚠️ Read `node_modules/next/dist/docs/` for static-export rules in Next 16 before changing config.
- **Dev:** `next dev` on `:3000` with rewrites `/api/*` and `/ws` → `http://127.0.0.1:7700`.

## 9.2 Client data flow

```
labSocket (WS, since-seq resume) ──► labStore.apply(event)      (pure reducers, zustand)
        │                                   │
        │ metrics frames                    ├──► React console (selectors, memoised)
        ▼                                   └──► Director (subscribes to the raw event stream + store)
metricsStore (per job: typed arrays)                 │
        └──► uPlot charts                             ▼
                                              Phaser scenes (entities, animations)
```

- `labStore` holds: projects, plans (DAG), agents (spec + status + current task + posterior summary), tasks, jobs (status + last metrics + forecast), approvals, memory hits, notes index, budget, telemetry, mode. **Every field is derivable from events** — reducers are pure and unit-tested with recorded event fixtures.
- `metricsStore` keeps per-job `Float32Array` columns (append-only, capacity-doubling) so uPlot redraws without allocations.
- Reconnect: §3.4.6. Duplicate events (seq ≤ last applied) are ignored.

## 9.3 Scenes

| Scene | Built from | Contents |
|---|---|---|
| `BootScene` | PokeStonks | font wait, first art step |
| `PreloadScene` | PokeStonks (extended) | procedural art steps + **load generated atlases** (`/assets/gen/manifest.json`) + build region & lab maps; progress bar tracks real work |
| `RegionScene` | `OverworldScene` (rewritten) | Region map (§2.5), Ash (player, grid-engine), agent entities (PMD walkers), buildings with warps (Lab, Pokémon Center, Library, Day Care, PC), gyms, docks (Kaggle/Colab), quest flags |
| `LabScene` | new (interior builder from `buildExchangeInterior`) | Oak, stations (library desk, code bench, env rack, quest board, Pokédex terminal, arena door), agent entities with bubbles, the door where wild Pokémon appear |
| `GymScene` | `BattleScene` (rewritten) | Leader + paper's Pokémon (front sprite) vs our runs (back sprites), plates (HP = budget / gap), dialog box narrating checkpoints, Oracle cone mini-chart, multi-run tabs (triple-battle layout for 3 concurrent runs) |
| Overlays | new | `EvolutionOverlay` (classic white-flash morph, ~4 s, skippable), `CatchOverlay` (Poké Ball throw, wobble ×3, click), `DayCareOverlay` (egg hatch), `FaintOverlay` (to PC) |

Scene switching follows the camera of attention: by default the desk shows **RegionScene** zoomed to the active town; entering the Lab or a Gym is automatic when the Director's "spotlight" rules fire (a spawn → Lab door; a hero run starts → Gym) unless the user has taken manual control (any key press pauses auto-spotlight for 20 s).

## 9.4 World entities

### 9.4.1 `AgentEntity`
- Sprite: PMD walker atlas for the species (`walk_<dir>`, `idle_<dir>`, `sleep`, `attack_<dir>`, `hurt_<dir>`), nameplate (`Charmeleon v2 · Lv 63`), status ring colour (idle grey / working blue / thinking yellow / error red), speech bubble (≤ 2 lines, 140 chars).
- Registered in grid-engine at runtime (`addCharacter`) on `agent.spawned`; removed on retire/merge after the overlay.

### 9.4.2 Capability → station (deterministic)

| Capability group | Station (Lab tile) | Region location when not in the Lab |
|---|---|---|
| `paper_read`, `spec_extract`, `claim_extract`, `literature_search`, `paper_discover` | Library desk | Pokédex Library |
| `implement`, `code_edit` | Code bench | — |
| `env_setup`, `dependency_fix`, `data_prep` | Server rack | — |
| `debug`, `repair` | — | Pokémon Center |
| `experiment_design`, `whatif_design` | Quest board | Safari Zone gate |
| `run_experiment` | Arena door | that paper's Gym |
| `compute_ops`, `remote_run` | Arena door | Kaggle dock / Colab cable car |
| `analyze`, `repro_compare`, `explain` | Analysis table | — |
| `report_write`, `notes`, `author_email` | Scribe desk | — |
| idle | — | campus lawn (sleep animation) |

### 9.4.3 Job entities
Running jobs appear in the Gym as battlers; on the Region map as a small flag over the Gym (local) or a boat/cable car (remote) with a progress pip.

## 9.5 The Director — event → animation, with honesty and pace

The Director is a small engine (`game/director/`) that converts events into **animation tasks** per entity:

```ts
interface AnimTask { entity: string; seq: number; kind: 'walk'|'bubble'|'anim'|'overlay'|'battle_turn'|'sfx';
                     minMs: number; maxMs: number; skippable: boolean; run(ctx): Promise<void> }
```

Rules:
1. **Per-entity FIFO** queues; entities animate in parallel.
2. **Real-time bound:** if an entity's queue lags the newest event by > 1.5 s, the Director **compresses** — walking becomes a poof-teleport, bubbles show only the latest text, battle turns are batched ("3 checkpoints: +12 % test acc").
3. **Overlays are global and serial** (one evolution at a time); queued overlays beyond 2 are summarised as toasts.
4. **Reconcile:** every 2 s each entity's visual state is compared with `labStore` truth (position/status/species); mismatches snap to truth. The game can lag briefly but can never *drift*.
5. **Spotlight:** chooses which scene/area the camera shows (priority: approvals > evolutions/spawns > hero run > newest project) — overridable by the user.
6. **Event-id overlay** (`Shift+E`): each running AnimTask renders its `seq` — the binding proof.

`GymScene` turn synthesis: every ~1.5 s, metric points since the last turn are aggregated into one turn — Δ(target metric) → damage to the leader's "gap HP", elapsed budget → our HP, events (super effective, confused, critical) per the binding table §2.7. Text comes from templates filled with the real numbers ("Charmeleon's run reached 87 % test accuracy! It's super effective!").

## 9.6 Sprites, sounds and the asset pipeline

`assets/build_atlases.py` (Python, Pillow; run by `just atlases`):

| Input | Output | Notes |
|---|---|---|
| Showdown `sprites/ani/<name>.gif`, `ani-back/` (Gen 5 animated) | `gen/battle/<name>_{front,back}.png` + Phaser atlas JSON with per-frame durations | Phaser cannot play GIFs; we unpack frames (`ImageSequence`), trim, pack in a strip |
| Showdown `gen5/`, `gen3/` statics | fallbacks (`<name>_{front,back}_static.png`) | Used if a GIF is missing or for "classic style" toggle |
| PMD SpriteCollab `sprite/<dex4>/{Walk,Idle,Sleep,Attack,Hurt}-Anim.png` + `AnimData.xml` | `gen/walk/<name>.png` + atlas JSON (`<anim>_<dir>_<frame>`) | Sheet = one column per frame and **1 or 8 rows; row order 0 Down, 1 DownRight, 2 Right, 3 UpRight, 4 Up, 5 UpLeft, 6 Left, 7 DownLeft**; frame size differs per animation (`FrameWidth/Height`); `<Duration>` is in **1/60 s ticks** (ms = d × 1000 / 60) → Phaser per-frame `duration`; resolve `<CopyOf>`. We use rows 0/2/4/6 for grid-engine's 4 directions. ⚠️ grid-engine's built-in walking-animation mapping (3 frames) does not fit PMD's 4-frame walks → `AgentEntity` plays animations itself from `movementStarted/movementStopped/directionChanged` events |
| Showdown trainers (`ash`, `oak`, `sabrina`, `ltsurge`, `blaine`, `brock`, `erika`, `nursejoy`, `bill`) | `gen/trainers/*.png` | portraits for dialog & VS (Showdown asks: credit the artists, do not edit) |
| pret/pokefirered `graphics/object_events/pics/people/*.png` (Red, Prof. Oak, Nurse Joy, gym leaders, NPCs) | `gen/people/<name>.png` + atlas | real FireRed overworld walkers: 16×32 frames in a 10-frame strip (down/up/left idle, 2 walk frames each for down/up/left, extra pose); right = flipX(left); palette index 0 = transparent → replaces the procedural Ash/NPC walkers |
| PokeAPI cries `<dex>.ogg` | `cries/<dex>.ogg` | played on spawn/evolve/select |
| `manifest.json` | species list = roster lines + Eevee forms + gym Pokémon | only what the lab uses (keeps load < 2 s) |

The PokeStonks procedural engines remain for tiles, buildings, Ash/NPC walkers, UI frames, music (title/overworld/battle/victory/defeat) and 26 SFX.

**Audio map:** overworld theme in Region/Lab; battle theme in Gym; victory jingle on badge; `levelup` SFX on reward > 0.7; `heal` on Medic fix; `faint` on retire; `encounter` on spawn proposal; species cry on spawn/evolve/selection (volume-ducked).

## 9.7 The console (React panels)

| Panel | Shows | Interactions |
|---|---|---|
| **HUD** (always) | LIVE/REPLAY, GPU %, VRAM, power warning, active jobs, approvals badge, tokens left (Elevate/Groq), compute saved | click → relevant panel |
| **Quests** | projects; plan DAG (React Flow) with step status, assigned agent, timings; plan revisions with diff | new request (text, drop PDF/CSV, repo path), redirect, pause/cancel |
| **Activity** | event feed with *why* (decision events show their rationale & model version); filters by project/agent/kind | jump to entity / job |
| **Team** | roster cards (species, version, level, posterior μ±σ, tasks, cost, format errors); **evolution lineage tree** (React Flow: refine edges, merge edges, retired greyed with reason) | feedback 👍/👎 on recent tasks, retire/refine manually |
| **Experiments** | live curves (uPlot) with Oracle cones; run table (config, device, target, status, best metric, GPU-s, saved); compare selected runs | kill, let-it-run, rerun, force-rerun (bypass dedup) |
| **Safari Map** | Navigator heatmap (μ, σ, acquisition), finished runs, next suggestions | accept/skip suggestion, set budget |
| **Repro Report** | verdicts per claim, evidence table, hypotheses with evidence scores & diagnostic runs, narrative | 👍/👎, open Markdown, export bundle |
| **Pokédex** | memory: lessons, fixes (success counts), configs (dedup index), papers | search, delete a wrong lesson (event) |
| **Library** | paper list; reader with highlighted claim/spec spans; discovered papers | ingest, "reproduce this" |
| **Notes** | project notes & reports (Markdown) | edit, save, export, share view link |
| **Compute** | pool slots, queue, Kaggle/Colab jobs, telemetry sparkline | pause pool, change slots |
| **Lab Brain** | each ML instrument: version, training size, CV metrics, learning-over-time chart, compute saved, tokens saved | retrain, view report |
| **Policy** | autonomy policy toggles (§6.2.7) | edit (event) |

## 9.8 The phone — Pokégear PWA (`/m`)

- Pair by scanning the console QR (§5.8). Installable PWA (`app/m/manifest.ts`), big touch targets, dark/light.
- Tabs: **Inbox** (approval cards: spawn / merge / remote job / question — Approve, Reject, *Reject with note*), **Projects** (status, current step, live best metric sparkline), **Control** (kill/let-run on running jobs, pause lab), **Redirect** (text box + 🎤 hold-to-talk → audio uploaded to labd → brain transcribes with Groq `whisper-large-v3` → `cmd.redirect`).
- Notifications: in-app banner + vibration while open (web push needs HTTPS + service worker; enabled when the tunnel provides HTTPS `[STRETCH]`).
- Same WS protocol with role `phone`.

## 9.9 Frontend performance rules

- Phaser at 60 fps with ≤ 12 agents + 3 battles: texture atlases only, no per-frame allocations, bubbles re-rendered only on text change.
- React panels never re-render on metric frames — charts subscribe to `metricsStore` directly (uPlot `setData` on rAF).
- Event feed virtualised (only visible rows rendered).
- Lazy-load heavy panels (React Flow, Markdown) with `next/dynamic`.
- Budget: initial load < 2.5 s from localhost; atlas payload < 15 MB.

## 9.10 Tests

- `vitest`: reducers (fixture streams → expected store), Director compression rules (synthetic lag), turn synthesis (metric deltas → expected dialog lines), capability→station mapping.
- Playwright: load `/replay/?session=demo_fixture` → assert scenes render, an evolution overlay plays, the Experiments panel shows the curve with a cone, event-id overlay lists seq numbers; phone flow (pair → approve) against a live labd with a fake brain.

---
