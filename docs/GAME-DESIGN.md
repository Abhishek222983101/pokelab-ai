# PokéLab — Game Design (build spec for the game layer)

Derived from `SYSTEM-ARCHITECTURE.md` §2 (concept, metaphor map, region, binding table) and §9 (scenes,
entities, Director, assets). This file turns those into concrete maps, characters, interactions and
screens. Every rule below obeys pillar **P1 Real or nothing**: nothing moves, fights, evolves or
speaks without a backend event behind it. Visual base = the PokeStonks engine (forked, §9.1):
procedural tiles, 3x camera, Press Start 2P, navy/gold dialogs, cream/slate plates, chiptune audio.

## 1. Experience flow

```
Title (React, PokéLab logotype, title theme)
  └─► Region: Pallet Campus (spawn outside Oak's Lab)          overworld theme
        ├─ Oak's Lab (interior, the heart: stations + Oak)       overworld theme
        ├─ Pokémon Center (Nurse Joy = Medic)                    heal jingle on fixes
        ├─ Pokédex Library (memory)
        ├─ Day Care (merges) · Bill's PC house (retired agents)
        └─ routes → 5 towns, each with a Gym ─► GymScene battle   battle theme
```
Layout modes (hotkeys **1/2/3**): Game (full screen), **Split** (game 60 % | console 40 %, demo
default), Console. The game is a static-export Next page served by labd; Phaser is client-only.

## 2. The world (maps; built with the PokeStonks `Builder`)

| Map | Theme | Size | Contains | Exits |
|---|---|---|---|---|
| **Pallet Campus** | bluechip | 48×36 | Oak's Lab (big, centre-north), Pokémon Center (red roof, west), Pokédex Library (east), Day Care (south-west, fenced yard), Bill's PC house (south-east), campus lawn (idle agents sleep here), signposts, lamps, flower beds, trees | N → Route 2/3 gate, W → Route 1, S-W → Modulo City, S-E → Edge Port |
| **Modulo City** | tech | 40×30 | **Sabrina's Gym** (Grokking / CPU-scale ML), server racks, Safari Zone gate (Navigator map) | back to Campus |
| **Edge Port** | energy | 40×30 | **Lt. Surge's Gym** (Distillation / edge ML), pumpjacks, docks, Colab Peak cable-car station | back to Campus |
| **Lumen Town** | meme (neon) | 40×30 | **Blaine's Gym** (Tiny NeRF / 3D), neon signs, rockets | back to Campus |
| **Crystal Cave** | crypto (obelisks = crystals) | 40×30 | **Brock's Gym** (Materials / Matbench) | back to Campus |
| **Arena Grove** | consumer | 40×30 | **Erika's Gym** (tabular comparison arena) | back to Campus |
| Interiors | per town | 12–20 × 9–14 | Oak's Lab, Pokémon Center, Library, Day Care, PC, each Gym lobby | door warps |

Kaggle Island / Colab Peak are shown as destinations on dock/cable-car signs; remote jobs render as
a boat/cable-car flag with a progress pip (§9.4.3).

### 2.1 New procedural tiles (appended to `art/tileset.ts`, painted in `tileProps.ts` style)
Buildings: Pokémon Center roof (red) + Poké Ball plate, Gym roof (slate/gold) + gym crest plate,
Oak's Lab plaque (flask), Library plaque (book), Day Care plaque (egg), PC plaque (monitor).
Lab interior: research desk + monitor, tall bookshelf (2 tiles), quest board (cork + note cards),
analysis table (charts), scribe desk (paper + quill), Pokédex terminal (2 tiles, screen glow),
arena door (Poké Ball door), Oak's starter table (3 Poké Balls), server rack (reused `RACK`).

## 3. Characters

| Who | Sprite | Where | Talk (Z) shows — always real data |
|---|---|---|---|
| **Ash** (player) | FireRed *Red* walker | spawns at the Lab door | — |
| **Prof. Oak** | FireRed Oak walker + portrait | Lab, behind his desk | active quest, current plan step, last Oak decision with its rationale |
| **Agents** | PMD walker of their species (§2.4), nameplate `Pikachu v2 · Lv 63`, status ring | at the station of their current task (§9.4.2); idle = asleep on the lawn | current thought (≤140 chars of real reasoning), capability, posterior μ±σ, tasks done, last reward |
| **Nurse Joy** (Medic) | FireRed walker | Pokémon Center counter | recent failures triaged, known fixes applied, zero-LLM triage count |
| **Bill** | FireRed walker | PC house | retired agents with retirement reasons |
| **Gym leaders** | FireRed walker + Showdown portrait | their Gym lobby | the paper's curated claim + our best run vs it |
| Townsfolk | PokeStonks procedural NPCs | towns | tips about controls / what the town studies (static text, clearly flavour) |

No random encounters, no wandering trainers that start battles — battles only exist when a job runs.

## 4. Mechanics — event → what happens (implements the §2.7 binding table)

| Event | In the world | Implementation |
|---|---|---|
| `agent.spawned` | Wild Pokémon appears at the Lab door → Poké Ball throw → joins | Catch overlay, then AgentEntity added to grid-engine |
| `agent.task_started` | Agent walks to its station (or teleports with a poof if > 1.5 s behind) | `stations.ts` → station tile → `moveTo` (Director) |
| `llm.call_started/finished` | "…" bubble on / off | bubble on entity |
| `agent.thought` | speech bubble with the real text | ≤ 2 lines, 140 chars |
| `agent.task_failed` / `job.failed` | hurt anim + red "!" → walks to Pokémon Center | Director sequence |
| `agent.rewarded` | level-up jingle, XP bar | nameplate level = μ×100 |
| `agent.evolved` | Evolution overlay (white flash morph, species swaps v→v+1) | only after shadow eval |
| `agent.merged` | both parents walk into Day Care, egg hatches | Day Care overlay |
| `agent.retired` | faint anim → sent to Bill's PC (reason shown) | Faint overlay |
| `job.started` (kit X) | flag over X's Gym; Gym battle becomes available | gym = kit → leader table |
| `job.metric` | in GymScene: turn synthesis every ~1.5 s | §5 |
| `job.done ok` & verdict | badge awarded, victory jingle | badge shown in HUD |
| `job.killed{oracle}` | "Got away safely!" + GPU-s saved | Retreat |
| `memory.hit` | Pokédex terminal glows, "Found in the Pokédex" | toast + terminal glow |

The **Director** (`lab/director`) owns the per-entity FIFO + compression; scenes only play what it
emits. `Shift+E` overlays each playing animation's event `seq` (AC-21).

## 5. Gym battle (GymScene = PokeStonks BattleScene renderer, new model)

- Arena background = the town theme's battle bg. **Foe** (top): the leader's ace (Showdown animated
  front sprite), plate `ALAKAZAM · SABRINA` with HP = **gap to the paper's claim** (100 % at start).
  **Ally** (bottom): the experimenter agent's Pokémon (animated back sprite), plate with HP =
  **remaining compute budget**, and the run's live metric `test_acc 0.87 / target 0.95`.
- Turn synthesis every ~1.5 s from the real metric points since last turn:
  Δtarget metric → damage to the leader's gap HP; elapsed steps/time → our HP drain;
  improvement > 3× rolling mean → "It's super effective!"; loss spike > 2σ → "… is confused!".
  Dialog text is templated from the real numbers ("Porygon's run reached 87.0 % test accuracy!").
- Menu (same 2×2 button layout as PokeStonks): **WATCH** (keep narrating), **STATS** (config, device,
  step, metrics table), **ORACLE** (forecast cone mini-chart, P(success)), **RETREAT** (kills the
  job via the real `kill_job` command → "Got away safely!").
- Win: job ok and metric ≥ claim → "SABRINA's ALAKAZAM fainted! You earned the MARSH BADGE"
  (badge per gym). Partial: "It's a draw — PARTIAL reproduction". Multi-run: up to 3 allies (triple
  layout) for what-if sweeps.

## 6. HUD

- **In-canvas (Phaser, PokeStonks Hud style):** top-left card = the spotlighted agent (portrait,
  name/version, role badge) or Oak when nobody is; top-centre banner = current map name; bottom
  controls bar `ARROWS MOVE · Z TALK · SHIFT RUN · TAB CONSOLE · SHIFT+E EVENTS`.
- **React overlay (PokeStonks HUD panel style, top-right):** LIVE/REPLAY badge, GPU %, active jobs,
  agents active/retired, approvals waiting, badges earned, mute, layout-mode buttons.
- Toasts (React): "A wild EEVEE appeared!", "Found in the Pokédex", "Got away safely! Saved 41 GPU-s".

## 7. Audio map (PokeStonks chiptune engine)
Title → `title`; Region/Lab → `overworld`; Gym → `battle`; badge → victory jingle; reward > 0.7 →
`levelup`; Medic fix → `heal`; retire → `faint`; spawn proposal → `encounter`; species cry on
spawn/evolve/selection (ducked). Mute button persists per viewer.

## 8. Camera & spotlight
Default: follow Ash at 3× (route) / 4× (interior). Spotlight rules (§9.5) may fade the view to the
Lab on a spawn or to a Gym when a hero run starts, unless the user pressed a key in the last 20 s.

## 9. Build order (each step screenshot-checked against PokeStonks before moving on)
1. Engine parity (fork renders identically) ✅
2. Pallet Campus map + new building tiles + warps to interiors
3. Oak's Lab interior with stations + Oak
4. AgentEntity with PMD walkers, driven by the store via `stations.ts` + Director
5. HUD (in-canvas + React panel), toasts, title screen, audio
6. GymScene battle bound to live job metrics; badges
7. Other towns + gyms; overlays (catch/evolve/faint/day care)
8. Console restyle in the same tokens; Split layout
