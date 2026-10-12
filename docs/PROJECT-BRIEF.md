# PokéLab — Project Brief (hand this whole file to another Claude session)

> Purpose: give a fresh Claude/engineer **complete, honest context** on this project — what it is, where everything
> lives, what really works, what does not, and how reusable it is — so it can be compared against another
> hackathon project and either plugged into or moved forward.
> Written 12 Oct 2026, after the Elevate 1.0 hackathon (DJSCE, 10–11 Oct 2026).

---

## 0. Links

| What | Link |
|---|---|
| **Your repo (canonical, most up to date)** | https://github.com/Abhishek222983101/pokelab-ai |
| Hackathon (college) repo, mirror | https://github.com/ELEVATE-1-0/ELEV04 (branches `main` and `dev`, kept in sync) |
| **Live desk (Vercel, static)** | https://pokelab-ai.vercel.app/lab/ (title page: `/`) |
| Vercel project | `pokelab-ai` in team `abhishek-s-projects-c6c0ff0c` |
| Local desk (the full stack) | http://localhost:7700/lab/ after `just live` |
| Public tunnel to the laptop backend | changes every start; `grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel.log` |
| W&B project (offline-logged runs, synced manually) | `forge.coreweave.com/wandb/abhisheksoni1445-mistralfluence/pokelab` |
| Problem statement | Elevate 1.0 **PS03 "An Evolving AI Research Environment"** (PDF: `Elevate 1.0 PS list.pdf`, pp. 5–7) |
| Full blueprint | `docs/SYSTEM-ARCHITECTURE.md` (≈2,600 lines; D1–D27 demands, AC-1…25 acceptance, build plan P0–P12) |
| Honest gap analysis | `docs/GAP-ANALYSIS.md` |
| Game design spec | `docs/GAME-DESIGN.md` |

**Important:** the Vercel site is **only a static front end**. The real work (Rust core, Python brain, GPU training)
runs on the laptop; the Vercel page reaches it through a Cloudflare quick tunnel whose address is baked into the
build. If the tunnel address changes, run `just deploy` (script `scripts/deploy_vercel.sh`). With the laptop off,
the page shows nothing live.

---

## 1. One-paragraph pitch

PokéLab is an **event-sourced, multi-agent ML research lab** skinned as a Pokémon game. A researcher types
"Reproduce grokking" (or "What if weight decay is zero?"). **Professor Oak** (a deterministic scheduler, not an LLM)
plans the work, picks agents (Pokémon) per step by sampling their learned reward posteriors, and the agents run
**real training jobs on the laptop GPU**. Every move, number and animation on screen is derived from a logged event
(`var/lab.db`) — nothing is scripted. Verdicts (REPRODUCED / PARTIAL / FAILED) come from comparing the measured
metric to the paper's claim.

## 2. What the problem statement (PS03) wanted

Build a research environment with a **dynamic team of AI agents** across the ML research lifecycle that: takes a
paper/idea, runs experiments on local/Kaggle/Colab compute, handles env/data/impl errors, has a **meta-controller**
choosing capabilities, **spawns/adapts** agents on skill gaps, evaluates agents with a **reward loop** (outcome, cost,
researcher feedback), **refines** good agents and **merges/retires** weak ones, goes beyond reproduction to
**what-if** studies and **explaining why results differ**, keeps **memory** across experiments, offers **mobile
control**, and an interface that shows what agents do, why, how they perform and how the team evolves — on modest
compute. Deliverables: ≥1 paper reproduced autonomously, ≥1 what-if investigated, an explanation of differences.

## 3. Architecture (three processes, one append-only log)

```
 browser (Next.js static export, Phaser room + React panels)
     ▲ WebSocket /api/ws (events out, commands in: request, feedback, kill_job)
     │
 labd  (Rust: axum, rusqlite, tokio)  ── SQLite WAL  var/lab.db  (table `events` = the single source of truth)
     │ /internal/brain (auth'd WS)                  │ job_submit
     ▼                                              ▼
 brain (Python: Oak runtime, agents, scheduler)    warm worker pool (Python, JSON-lines over stdio)
                                                    └ kits: grokking, distillation, nerf, materials, arena, smoke
```
- **Event sourcing:** every state (agent level, plan status, map tiles, paper evidence) is a *fold* of events:
  `brain/pokelab_brain/state.py` (Python) and `web/lib/labReducer.ts` (pure reducer, TypeScript). Replaying the log
  rebuilds identical state; restarts lose nothing.
- **Rule:** nothing on screen exists without an event behind it (Shift+E overlay, click-to-expand "PROOF" on every
  activity row shows the logged JSON).
- **Contracts:** `contracts/pokelab_contracts` (+ generated schemas) share event/command types across Rust/Python/TS.

### Stack & versions
Rust (axum, rusqlite, tokio, tower-http), Python 3.13 (uv, pytest, pypdf, scikit-learn, torch via workers venv),
TypeScript: Next **16.3.8**, React 19.2, Phaser **3.80.1**, grid-engine **2.45.0**, zustand, Tailwind v4, vitest.
~3.4k LOC Rust, ~13k Python, ~17.5k TS/TSX. Hardware used: laptop with NVIDIA RTX 5050 (8 GB), CUDA.

## 4. How it works at runtime (the Oak loop)

1. UI sends WS command `request {text}` → labd records `project.requested`.
2. Brain (`oak/runtime.py`) sees it. Intake maps words → one of 5 paper packs (`oak/kits.py`: grokking, distillation,
   nerf, materials, arena); LLM (Elevate gateway → Groq fallback) only as intake fallback. "what if / explore" →
   `oak/whatif.py`; "reset team" → de-evolve.
3. `project.created` + a 9-step plan (template `oak/templates/reproduce.yaml`).
4. `oak/scheduler.py` runs steps: for each, candidates = agents with the capability; **Thompson sampling**
   (`labml/selector/thompson.py`) picks; emits `agent.task_started` (with candidate posteriors), `agent.thought`
   (text built from real results by `narrate_step`), then the **real executor** (`oak/executors.py`), verifier checks
   (`agents/verifiers.py`), `agent.task_finished|failed`, `agent.rewarded` (reward_v2 breakdown). Steps are paced
   (`POKELAB_STEP_DWELL_S`, default 2.5 s) so humans can see agents work.
5. Executors: **paper_read** (pypdf extract + chunk the real PDF — grokking only; others use curated packs →
   `paper.ingested`), **spec_extract** (`claim.extracted`), **implement** (validates kit config), **env_setup**
   (smoke job), **run_experiment** (real kit job via labd warm pool → `job.started/metric/done`), **analyze**
   (`analysis.computed`: step train≥0.99, step test≥claim, delay), **repro_compare** (verdict), **report_write**
   (`var/projects/<id>/report.md`).
6. `project.completed {verdict,value,claim}` → `project.badge_awarded` if REPRODUCED. Then **rule-based evolution**:
   an agent with ≥ N rewarded tasks (default 8; demo 3 via `POKELAB_EVOLVE_MIN_REWARDS`) and mean reward ≥ 0.90
   evolves to the next species in its line (`agent.evolved`, evidence in payload). `agent.devolved` resets for demos.
7. **What-if** (`oak/whatif.py`): grid weight-decay {0, 0.3, 1.0} × data-fraction {0.3, 0.5}; each cell = a real
   grokking job; events `explore.planned/cell/analysis`; the Safari tab renders the tiles and computed findings.

### The five real paper kits (all verified live on 11 Oct)
| Kit | Paper | Measured vs claim |
|---|---|---|
| grokking | Power et al. / Nanda et al. (modular addition, MLP/transformer) | test_acc 0.991 vs 0.95 (grok step ≈1900; train saturates ≈100) |
| distillation | Hinton et al. KD on MNIST subsample | 0.8985 vs 0.88 |
| materials | superconductor Tc (Matbench-style), gradient boosting | R² 0.906 vs 0.90 |
| arena | Grinsztajn et al. tree vs MLP, paired t-test | 0.8515 vs 0.84 |
| nerf | Mildenhall et al. tiny NeRF (lego) | PSNR 17.9 vs 15 |

## 5. The "ML" in the project — honest inventory

| Component | What it is | Used in the live demo? |
|---|---|---|
| 5 kit trainers (`workers/pokelab_workers/kits/*`) | Real PyTorch/sklearn training | **Yes** (core evidence) |
| Selector — Beta-Bernoulli **Thompson sampling** (`labml/selector`) | Agent choice from reward posterior | **Yes**, but each capability has only one agent, so it never really chooses |
| Reward v2 (`brain/reward_v2.py`) | quality/success/time/cost/human | Yes, but time/cost inputs are placeholders (levels saturate ~90–99) |
| Oracle (`labml/oracle`) — GBM/logistic early-stop predictor | trained on ~4–5 real curves; no AUROC | **No** (built + unit-tested) |
| Navigator (`labml/navigator`) — GP + UCB | 1-D knob only | **No** |
| Medic (`labml/medic`) — regex failure classifier, zero-LLM | | **No** |
| Scout (coverage gaps), Compute Router (rules), Analysts (FFT grok signature) | | Scout runs but never fires; others **No** |
| LLM router (Elevate → Groq, cache, budget) | | intake fallback + lifecycle drafting only |

**Agents are not LLMs.** They are deterministic executors with a Pokémon identity; "context" = their logged task
history and reward record (rebuilt from events). There is no long-term memory across papers, no learning of new
methods. Evolution is rule-based (the designed GEPA-style refine + shadow-eval exists as code, not wired).

## 6. UI (what you can click)

`/lab/` desk = room scene (Phaser, agents walk to stations) + console tabs: **TEAM** (inspector: reward posterior,
lineage, work log, 👍/👎), **QUESTS** (plan checklist), **PAPER** (real extracted paper text, claim, measured
analysis), **ACTIVITY** (click a row → logged event JSON + related events), **EXPERIMENTS** (live curve vs claim,
shaded memorise-then-generalise region, run table with verification), **SAFARI** (the what-if map), **REPRO**
(verdict). Top HUD: LIVE/REPLAY badge, GPU/VRAM from `/api/telemetry` (nvidia-smi), jobs, badges. Over the room:
NOW card (current step, agent, live metric vs claim). "Ask Oak" box + quick prompts + "De-evolve team" button.
`/m/` phone page (pair + kill only), `/console/` older console, `/game/` forwards to `/lab/` (the planned Region/Gym
scenes are not connected to events).

## 7. Status vs PS03 (priority order)

| # | Demand | Status |
|---|---|---|
| 1 | Reproduce a paper autonomously (D22) | ✅ 5 papers live |
| 2 | What-if extension (D14/D23) | ✅ real 6-run grid (new) |
| 3 | Explain why results differ (D13/D24) | 🟡 computed findings from the grid; `science/comparator_v2.py` (17-item checklist + hypotheses) built but not wired |
| 4 | Dynamic team: spawn/refine/merge/retire (D7/D9/D10) | 🟡 rule-based evolve/de-evolve live; spawn/merge/retire exist as code+tests, never fire |
| 5 | Reward loop with researcher feedback (D8) | 🟡 live, with placeholder time/cost inputs |
| 6 | Memory/dedup across runs (D15) | ❌ repeat request re-runs training (`pokedex.py` is an unwired lessons store) |
| 7 | Kaggle/Colab/remote (D3) | 🔧 runners tested, not used live |
| 8 | Mobile control (D18) | 🟡 pair + kill only |
| 9 | Accept dataset/repo/idea inputs (D2) | 🔧 modules exist, unwired; only the 5 named papers |
| 10 | Large-scale concurrent agents UI (D25) | 🟡 9 agents, one project at a time |

**Biggest honest weaknesses:** (a) one agent per capability ⇒ selection is vacuous; (b) reward inputs are constants;
(c) most Phase 5–7 modules are unit-tested but not called by the live loop (the repo's own "14 real acceptance
criteria" means *tested*, not *demonstrated*); (d) the PokeStonks-style walkable world (RegionScene/GymScene) is not
built — maps, tiles and sprite pipelines exist (`web/game/overworld`, `web/game/art`), scenes do not; (e) Pokédex
memory/dedup absent. Full table: `docs/GAP-ANALYSIS.md`.

## 8. Bugs found and fixed late (useful lessons)
- labd treated any non-text frame (the Python client's keep-alive ping) as a hang-up → brain dropped ~20 s after
  connecting and silently stalled. Fixed + regression test `brain_keepalive`.
- Brain never noticed a dead socket → `subscribe()` now raises so `main.run` reconnects.
- labd job ids restarted at `job-1` each boot → brain read stale `job.done`. Ids now continue from the event log.
- Interrupted projects left "ghost" quests → `project.abandoned` on boot.
- `just test` collected all Python projects into one venv → now per-project.

## 9. Repo map
```
core/crates/{labd,lab-gateway,lab-jobs,lab-store,lab-metrics,lab-telemetry}   Rust core (tests in crates/*/tests)
brain/pokelab_brain/{oak,agents,llm,papers,science,memory,state.py,bus.py,main.py,acceptance.py}
labml/pokelab_labml/{selector,oracle,navigator,medic,scout,router,analysts}
workers/pokelab_workers/{pool_main.py,kits/*,remote/}
contracts/  config/{lab,llm,papers,roster}.toml  data/papers/*.pdf (8 PDFs; only grokking's is ingested)
web/app/{lab,m,console,game,components}  web/lib/{labReducer,liveView,labSocket,store,useLabConnection}.ts
web/game/{labroom (the room scene),art,audio,battle,overworld,scenes}  web/lab/{gyms,placement,stations,director}
scripts/{live_up.sh,deploy_vercel.sh,chaos/,fetch_*.sh,run_acceptance_suite.py}  docs/  justfile
```
Not in git (generated/large/secret): `.env`, `var/` (databases, projects, wandb), `web/public/assets/gen` (sprite
atlases, built by `just atlases` from fetched sprites), `data/` datasets, node_modules, venvs.

## 10. Run it
```bash
just init && just fetch && just atlases      # once: env, datasets/papers/sprites, sprite atlases
cd web && npm install && npm run build && cd ..
just live                                    # restarts labd + brain (+ tunnel) and prints the links
# open http://localhost:7700/lab/  → click "Reproduce grokking"
just deploy                                  # redeploy the Vercel desk against the current tunnel
```
Tests: `cd web && npx vitest run` (66) · `cd brain && uv run pytest -q` (~225; includes real GPU runs) ·
`cd core && cargo test` · `cd contracts && uv run pytest`. Needs `.env` (LLM keys optional: without them Oak only
accepts requests that name a known paper). Never commit `.env`.

## 11. Demo script (5 min)
1. Open `/lab/` → LIVE badge, GPU/VRAM. 2. "Reproduce grokking" → NOW card, agents walk, PAPER tab (real PDF text +
measured delay). 3. ACTIVITY → PROOF on a row. 4. "What if weight decay is zero?" → SAFARI tiles fill in.
5. Click an agent → work log + lineage. 6. De-evolve, run once, watch evolve again.
**Say:** 5 papers reproduce on a laptop GPU with measured verdicts; event-sourced and replayable; learned selection +
rule-based evolution. **Don't say:** agents write code from papers; spawn/merge/memory/Kaggle are live.

## 12. Reuse guidance (for comparing with another project)
**Strong reusable assets:** the event-sourced core (`labd` + contracts) and brain fold pattern; the scheduler with
Thompson selection + verifier checks + narrated events; the warm GPU worker pool and kit interface (add a kit = add a
folder); the `/lab` desk (reducer → panels → proof drawers) which is generic to *any* "agents doing real work"
product; chaos drills and the acceptance-evidence framework.
**Costly to extend:** the Pokémon-specific art/maps (copyright-adjacent sprites, fetched not committed); the
unwired ML instruments (need real data volume to be meaningful); the not-built Region/Gym scenes.
**If plugging into another project:** reuse `labd` + `contracts` + `web/lib/labReducer.ts` + `web/app/lab` and write new
executors/kits; keep the "nothing on screen without an event" rule — it is the project's credibility.

## 13. Next steps (ordered)
1. Real reward inputs (measured wall-time/GPU-s) + a second agent for ≥3 capabilities → selection becomes real.
2. Wire `comparator_v2` + diagnostic runs → full "why do we differ from the paper" table.
3. Pokédex config-hash dedup (`job.deduped`, `memory.hit`) → repeat requests return instantly.
4. Wire Medic into the retry path; scripted spawn demo (uncovered capability → proposal → approve → join).
5. Wire Oracle early-stop with `gpu_s_saved`; Navigator on the what-if grid.
6. Paper Library: ingest any local PDF + LLM claim extraction + new kit adapters.
7. RegionScene/GymScene (walkable world, gym battle from `job.metric`) per `docs/GAME-DESIGN.md`.
8. Hosting: move labd+brain+worker to a GPU host so the Vercel site is not tied to a laptop tunnel.

## 14. Credits / licensing
Engine forked from PokeStonks (Phaser 3 + grid-engine, web3 stripped). Pokémon sprites/cries come from public fan
mirrors (PokeAPI / Showdown / PMDCollective) fetched locally for a non-commercial demo and **not committed**. Papers:
Power et al. 2022 (Grokking), Nanda et al. 2023, Hinton et al. 2015, Mildenhall et al. 2020, Hamidieh 2018,
Grinsztajn et al. 2022.
