# PART 2 — THE PRODUCT & THE EXPERIENCE

## 2.1 One sentence

**PokéLab is an evolving multi-agent ML research lab you can watch, play and steer like a Pokémon game: Professor Oak (the meta-controller) staffs research quests with Pokémon (AI agents), every battle is a real training run on real hardware, every evolution is a measured agent improvement, the Pokédex is the lab's memory — and seven small ML models trained on the lab's own history make it faster and smarter with every run.**

## 2.2 Design pillars (every later decision defers to these)

| # | Pillar | Means in practice |
|---|---|---|
| P1 | **Real or nothing** | The game only *renders* backend events. No timers that fake progress, no canned animations without a cause. Idle lab = sleeping Pokémon. |
| P2 | **Never buffer** | Warm GPU workers (< 0.3 s to start a kit job), cached LLM answers, ML decisions in milliseconds, LLM latency covered by *real* intermediate state. |
| P3 | **The lab learns** | Every decision/run/failure is an event; every learned component retrains in the background (< 1 s) and its improvement is charted. |
| P4 | **Human in command** | An explicit autonomy policy decides what needs approval; approve/reject/redirect/kill work from desk and phone in < 1 s. |
| P5 | **Honest science** | Numbers carry provenance (run id, seed, device, config hash). Memory hits and replays are labelled. Claims in reports are checked against the evidence table. |
| P6 | **Fail soft** | Any process can die and come back; the event log is the truth; provider fallbacks and replay mode keep the demo alive. |

## 2.3 The metaphor map (locked)

| PS concept | In PokéLab | Bound to (real backend state) |
|---|---|---|
| The researcher | **Ash** (the player avatar you walk with) | Human commands: requests, approvals, redirects, feedback |
| Meta-controller | **Professor Oak** | `brain/oak/*`: capability analysis, planning, selection, lifecycle (§6.2) |
| Agents | **Pokémon** (roster §2.4) | `AgentSpec` rows (§6.4): role, capabilities, prompt, model tier, version, lineage, stats |
| Agent selection | Oak "sends out" a Pokémon | Selector posterior draw (§7.3) — the choice card shows the numbers |
| Agent level / XP | Level & XP bar | Posterior mean reward ×100 / number of rewarded tasks |
| Spawn new specialist | **"A wild Eevee appeared!" → Poké Ball** | Scout skill-gap detection (§7.5) + approval → new spec inserted |
| Adapt / refine | **Evolution** (Charmander → Charmeleon) | GEPA-lite reflection + shadow evaluation passed (§6.8.3) |
| Merge | **Day Care** (two enter, an egg hatches) | Merge policy + approved merged spec (§6.8.4) |
| Retire | **Faints → sent to Bill's PC** | Posterior below threshold with confidence (§6.8.5) |
| Research domain | **Town** with a **Gym** | Paper pack domain (Part 8) |
| Paper's claimed result | **Gym Leader** | `PaperPack.claims[]` (§6.6) |
| An experiment run | **A Gym battle** | A job: HP of *our* side = remaining compute budget; HP of the *leader* = remaining gap to the paper's number |
| A what-if sweep | **Triple battles / tournament bracket** | Concurrent jobs designed by the Navigator (§7.2) |
| Early stop of a doomed run | **"Got away safely!"** | Oracle P(success) below threshold → kill (§7.1) |
| The hypothesis space | **Safari Zone map with fog of war** | Navigator Gaussian-process posterior (§7.2) |
| Memory | **Pokédex** | Event log + config-hash index + lessons + fix library (§6.7) |
| Debugging | **Pokémon Center (Nurse Joy = Medic)** | Failure triage + fix recall (§7.4) |
| Remote compute | **Kaggle Island / Colab Peak** (boat/flight) | Remote runners (§8.8) + Compute Router (§7.7) |
| A reproduced paper | **Badge** | Comparator verdict REPRODUCED/PARTIAL with evidence (§6.10) |
| Phone control | **Pokégear** | Mobile PWA `/m` (§9.8) |
| Lab memory browsing | **Pokédex terminal** | Memory views (§9.7) |

## 2.4 The cast — base roster and evolution lines

All Pokémon are Gen 1–2 (sprites already mirrored in `assets/vendor/showdown/`, walking sprites from PMD SpriteCollab, §9.6). A line's stage = the agent's **version**; evolving means a *promoted* refinement. Species are configuration, not code (`brain/config/roster.toml`).

| Role (capabilities) | Line (v1 → v2 → v3) | Why this Pokémon |
|---|---|---|
| **Paper Reader** (`paper_read`, `spec_extract`, `claim_extract`) | Pichu → **Pikachu** → Raichu *(seeded at v2: it was refined once during the build — real history, logged)* | The user's pick; Electric = fast reader |
| **Implementer** (`implement`, `code_edit`) | **Charmander** → Charmeleon → Charizard | The user's pick; Fire = forging code |
| **Environment Engineer** (`env_setup`, `dependency_fix`, `data_prep`) | **Bulbasaur** → Ivysaur → Venusaur | Grows the roots everything stands on |
| **Debugger** (`debug`, `repair`) | **Squirtle** → Wartortle → Blastoise | Washes bugs away |
| **Analyst / Comparator** (`analyze`, `repro_compare`, `explain`) | **Abra** → Kadabra → Alakazam | The Psychic brain that sees hidden structure |
| **Experimenter** (`experiment_design`, `run_experiment`, `whatif_design`) | **Porygon** → Porygon2 | A digital creature that lives in machines |
| **Compute Runner** (`compute_ops`, `remote_run`) | **Magnemite** → Magneton | Electric/Steel — hardware |
| **Scribe** (`notes`, `report_write`, `author_email`) | **Hoothoot** → Noctowl | The scholarly owl |
| **Scout** (`literature_search`, `paper_discover`) | **Zubat** → Golbat → Crobat | Echolocation = search |
| **Spawned specialist** (any new capability) | **Eevee** → evolves by specialisation: **Espeon** (theory/maths), **Jolteon** (edge/efficiency), **Flareon** (3D/rendering), **Vaporeon** (materials/chemistry), **Umbreon** (robustness/debugging) | Eevee *is* "adapt to what is needed" |

| Character | Sprite | Role |
|---|---|---|
| **Ash** | `trainers/ash.png` (portrait) + FireRed **Red** overworld walker (pret/pokefirered) | The researcher (player) |
| **Professor Oak** | `trainers/oak.png` + FireRed Prof. Oak walker | Meta-controller avatar; speaks Oak's decisions |
| **Nurse Joy** | trainer sprite (Pokémon Center) | Voice of the Medic |
| **Bill** | trainer sprite | Keeper of the PC (retired agents, archives) |
| **Gym leaders** | Sabrina (Grokking/CPU-ML), Lt. Surge (Edge ML), Blaine (3D/NeRF), Brock (Materials), Erika (comparison arena) | Each speaks for a paper's claims |

## 2.5 The world: the Research Region

```
                          ┌───────────────────────┐
                          │     KAGGLE ISLAND      │ ◄── boat dock (remote jobs sail here)
                          └───────────▲───────────┘
   ┌───────────────┐                  │                  ┌────────────────┐
   │  CRYSTAL CAVE │                  │                  │   LUMEN TOWN   │
   │  (Materials)  │◄──── Route 2 ────┼──── Route 3 ────►│   (3D / NeRF)  │
   │  Brock's Gym  │                  │                  │  Blaine's Gym  │
   └───────┬───────┘        ┌─────────┴─────────┐        └───────┬────────┘
           │                │   PALLET CAMPUS   │                │
           │                │ ┌───────────────┐ │                │
           └──── Route 1 ───┤ │  OAK'S LAB    │ ├─── Route 4 ────┘
                            │ │ (HQ, stations)│ │
                            │ └───────────────┘ │
                            │ Pokémon Center ✚  │   ← Medic / debugging
                            │ Pokédex Library 📖 │   ← memory
                            │ Day Care 🥚 · PC 💾│   ← merges · retired agents
                            └───┬───────────┬───┘
                ┌───────────────┘           └──────────────┐
       ┌────────┴───────┐                         ┌────────┴────────┐
       │  MODULO CITY   │                         │   EDGE PORT     │
       │ (CPU-scale ML) │                         │ (Edge & efficient│
       │ Sabrina's Gym  │                         │  ML) Surge's Gym│
       │ Safari Zone 🌫 │ ← Navigator map          └─────────────────┘
       └────────────────┘                      ▲ COLAB PEAK (cable car)
```

- Built with the PokeStonks procedural map builder (`maps.ts` `Builder`), themes reused: Modulo City = `tech`, Edge Port = `energy`, Lumen Town = `meme` (neon), Crystal Cave = `crypto` (obelisks read as crystals), Pallet Campus = `bluechip`.
- **Where an agent stands is a pure function of its current task** (§9.4.2): `paper_read` → Lab library desk; `implement` → Lab code bench; `env_setup` → Lab server rack; `debug` → Pokémon Center; `run_experiment` → the paper's Gym; `remote_run` → Kaggle Island / Colab Peak; memory work → Pokédex Library; idle → asleep on the campus lawn. No randomness decides positions.

## 2.6 Three zoom levels + two control surfaces

| Level | Scene | Shows (PS) | Reads from |
|---|---|---|---|
| **L1 Region** | `RegionScene` | *All* research at once: every agent's location = its current task; projects as quest flags on towns; jobs as boats/cable cars to remote compute; badges `[PS-D25]` | Agents, tasks, jobs, projects |
| **L2 Oak's Lab** (the heart) | `LabScene` | One project in detail: stations, the quest board (plan DAG), Oak's choice cards, speech bubbles with the agent's *current thought*, wild-Pokémon spawns at the door, evolutions `[PS-D5,D6,D7,D9,D26]` | Plan, agent thoughts/actions, selections, lifecycle |
| **L3 Gym battle** | `GymScene` | Experiments: our runs vs the paper's claim; HP = budget vs gap; Oracle cone; "super effective!" on real jumps; retreats on early stops `[PS-D11,D14,D19,D23]` | Job metrics (downsampled), forecasts, kills |
| **Console (PC/Pokégear)** | React panels | The serious instrument: quest log, activity feed with *why*, team & lineage, live curves, Safari map, Repro report, Pokédex, Library, Notes, Compute, Budget, Autonomy policy `[PS-D17,D20,D25–27]` | Same store |
| **Phone (Pokégear app)** | `/m` PWA | Approvals inbox, project status, kill/pause, redirect by text or **voice** (Whisper on Groq) `[PS-D18,D20]` | Same store, via tunnel/LAN |

Layout modes (hotkeys `1/2/3`): **Game** (full-screen game + slim HUD), **Split** (game 60 % | console 40 % — the demo default), **Console** (full instrument). The HUD always shows: LIVE/REPLAY badge, GPU utilisation, active jobs, approvals waiting, tokens left today, power mode warning.

## 2.7 The binding table — what each visual means (and which event causes it)

| On screen | Cause (event kind, §10.2) | Rule |
|---|---|---|
| Pokémon walks to a station | `agent.task_started` (capability → station map) | Path via grid-engine `moveTo`; if > 1.5 s behind real time, *poof-teleport* (Director time compression, §9.5) |
| "…" bubble | `llm.call_started` for that agent | Removed on `llm.call_finished` |
| Thought bubble text | `agent.thought` (≤ 140 chars of the agent's *actual* reasoning) | Never invented |
| Working animation (PMD *Attack/Charge*) | `agent.action` in progress | Stops on `agent.action_result` |
| Hurt animation + red "!" | `agent.task_failed` / `job.failed` | Followed by walk to Pokémon Center if Medic routes it |
| Level-up jingle, XP bar fills | `agent.rewarded` | Shows reward breakdown tooltip |
| Wild Pokémon at the door | `agent.spawn_proposed` | Poké Ball throw only after `human.approved` → `agent.spawned` |
| Evolution animation | `agent.evolved` | Only after shadow eval passed |
| Egg at Day Care | `agent.merged` | Parents walk in first (from `agent.merge_proposed`) |
| Faint + into PC | `agent.retired` | Shows reason text |
| Gym: our attack lands | `job.metric` checkpoint where the target metric improved | Damage = Δmetric normalised to the gap |
| "It's super effective!" | improvement > 3× rolling mean improvement (e.g. the grok jump) | — |
| "X is confused!" | loss spike > 2σ (e.g. slingshot) | — |
| Our HP drains | elapsed budget fraction | Exact |
| "Got away safely!" | `job.killed{reason:"oracle_early_stop"}` | Shows GPU-seconds saved |
| Badge | `project.badge_awarded` (comparator verdict) | — |
| Pokédex glow + "Found in the Pokédex" | `memory.hit` | Shows the original run id |
| Fog lifts on Safari map | `ml.navigator_updated` | Tiles = GP posterior |
| Boat sails to Kaggle Island | `compute.route_decided{target:"kaggle"}` + `job.started` | Returns on `job.completed` |

A debug overlay (`Shift+E`) prints the event `seq` next to every animation that is playing — the honesty proof for judges (AC-21).

## 2.8 What PokéLab is not

| It is not | Why |
|---|---|
| A chat app with a game skin | The main surfaces are the world, the console instruments and the phone; chat is one input among many (`cmd.ask`). |
| A fixed pipeline of hard-coded agents | Agents are data; the team at the end of the demo is not the team at the start. |
| An LLM that "grades itself" | Rewards come from objective verifiers first (§6.9); LLM-judging is a minority, flagged term. |
| A pre-recorded animation | Runs are live on the GPU (62 s for the full grokking reproduction, `[MEASURED]` plugged in); REPLAY mode exists only as a labelled fallback. |
| A custom-trained "AI brain" replacing the LLM | LLMs read, plan, code and explain; small ML models do what LLMs are bad at — calibrated numbers, fast routing, forecasting, statistics (Part 7). |

---
