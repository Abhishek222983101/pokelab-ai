
---

## P5 — The ML layer: Oak's Instruments ★★★★★ 🧠

> Read Part 7 completely before starting. Every model ends with an entry in `var/reports/labml.json` and a W&B run.

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P5.1** | Curve library sweep | ★★★ · 🔵 · 🔥 🧠 | `labml/oracle/library.py` + `just library`: Sobol designs of §7.1.4 submitted as `source=library_sweep, priority=background` jobs through labd (so they're preemptible and appear in the Pokédex); resumable; grouped train/val/test split by config written to `var/labml/splits.json`. Runs while you build P5.2+. | ≥ 300 MLP + ≥ 30 transformer runs complete; every run has metrics + telemetry; outcome labels (grokked? step?) computed |
| **P5.2** | Oracle (gbm + seq + param) | ★★★★★ · 🟣 · 🔥 🧠 | Features §7.1.1 (incremental, identical code for training and live — one function `features(prefix, cfg)`); `oracle-gbm` classifier + quantile regressors + isotonic calibration; `oracle-seq` temporal CNN (GPU, ~30 s); `oracle-param` fallback; grouped CV; model selection; early-stop simulation & operating point (wrong kills ≤ 2 %); learning-over-time curve; live service `oracle_watch` emitting `job.forecast` every 2 s and kill recommendations per §7.1.3. ⚠️ Leakage traps: never use features computed after the prefix; split by config not by run; calibrate on out-of-fold predictions only. | `labml.json#oracle` written (AUROC@20 %, Brier, MAE, compute saved, wrong kills, baselines, learning curve); live forecasts on a running job update every 2 s in < 5 ms each |
| **P5.3** | Navigator | ★★★★ · 🟣 · 🧠 | numpy GP (Matérn-5/2 + white, ML-II with restarts), straddle acquisition with batch local penalisation (§7.2.1), multi-fidelity labels from Oracle `p_success` for killed runs, time-to-grok GP; space proposal validated against kit config; simulation harness vs grid/random/Optuna TPE on the library ground truth; `ml.navigator_updated` events with a coarse grid for the UI. | `labml.json#navigator` shows runs-to-F1≥0.9 for all four strategies; live `explore` project produces suggestions in < 50 ms |
| **P5.4** | Bug Gym + Medic | ★★★★ · 🔵 · 🔥 🧠 | `scripts/bug_gym.py`: ~15 fault types × variants injected into kits/scripts (§7.4.2) → real failures with verified fixes (`source=bug_gym`); `labml/medic/*` normalisation, signatures, kNN, logistic classifier, policy (§7.4.1); integration in brain on `job.failed`; fix library writes on verified success. | `labml.json#medic` (top-1 accuracy, % auto-fixed without LLM, triage latency, tokens saved); AC-13 passes |
| **P5.5** | Selector | ★★★ · 🔵 · 🧠 | Beta-Thompson with discount, priors (§7.3.2), LinTS context once n ≥ 30, UCB1 ablation, replay simulation harness; replaces the P4.7 interim selector; posteriors in `oak.selection`. | `labml.json#selector` (cumulative reward vs round-robin/greedy/UCB1); AC-6 |
| **P5.6** | Scout | ★★★ · 🔵 · 🧠 | Capability embeddings, coverage, failure clustering, redundancy detection (§7.5); a labelled set of 40 requirement/roster pairs (`labml/scout/labels.yaml`); threshold tuning. Replaces the P4.5 stub. | `labml.json#scout` precision/recall; a materials request yields a gap, a grokking request does not |
| **P5.7** | Compute Router | ★★ · 🔵 · 🧠 | Runtime/VRAM regressors from all finished jobs; placement rule (§7.7) with measured remote overheads (Kaggle ~40 s; Colab measured in P10); `compute.route_decided` events. | `labml.json#router` MAPE; long jobs are routed remote when slots are full |
| **P5.8** | Analysts | ★★★ · 🔵 · 🧠 | `grok_fourier` (key frequencies, neuron clusters, restricted/excluded loss, Gini — reusing P2.4 code), plus stubs for the P11 analysts; artifacts + `analysis.ready`; comparator consumes them. | Analysis of the reference run shows 3–6 key frequencies and the precursor lead; PNGs saved |
| **P5.9** | labml CLI, registry, reports, W&B | ★★ · 🔵 · 🔑 | `pokelab_labml.cli` (`train-all`, `eval`), `registry.py` (versioned files + meta), online retraining loop in the brain (§7.9) with atomic swap; every training run logged to W&B. | `just labml` reproduces `labml.json` from scratch; brain loads all models in < 1 s |

**Exit:** the lab forecasts, prunes, explores, heals, selects and routes with measured models; AC-6, AC-13, AC-14, AC-15 pass.

---

## P6 — Lifecycle & evolution ★★★★☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P6.1** | Policy & approvals | ★★★ · 🔵 | `oak/policy.py` (§6.2.7) with live edits (`cmd.policy_set`), approval futures, expiry defaults, veto windows; approval events. | Approve/reject/expire paths tested with a fake client |
| **P6.2** | Spawn | ★★★ · 🔵 · 🔑 | Trigger evaluation (§6.8.1) using the Scout; ADAS-style spec drafting (§6.8.2) with the archive of past spawns; Eevee species + domain evolution table; prior inheritance; `agent.spawn_proposed/spawned`. | AC-7 (with desk approval; phone in P10) |
| **P6.3** | Refine (GEPA-lite) + shadow eval | ★★★★★ · 🟣 · 🔑 | Trace collection, reflection prompt, candidate spec, **shadow evaluation** on ≤ 4 recorded tasks (replay tool observations from the event log; reuse jobs via dedup; LLM cache disabled only for the candidate), Pareto acceptance (§6.8.3), `agent.evolved` / `refine_rejected`, species evolution, posterior restart. | AC-8: one promoted and one rejected refinement recorded with evidence |
| **P6.4** | Merge & retire | ★★★ · 🔵 · 🔑 | Redundancy detection → merge synthesis → shadow eval → `agent.merged`; retirement rule (Beta CDF) → `agent.retired`; task reassignment. | AC-9, AC-10 |
| **P6.5** | Reward v2 & feedback | ★★ · 🔵 | Project-level credit (§6.9), human feedback ingestion (`human.feedback` → H term → posterior), reward breakdown events. | AC-11: a 👎 lowers the posterior mean measurably |
| **P6.6** | Lifecycle simulation test | ★★★ · 🔵 | A seeded simulation with synthetic agents of known quality over 200 tasks: good agents promoted, bad retired, duplicates merged — guards against oscillation. | Simulation assertions green |

---

## P7 — Science & the research workspace ★★★☆☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P7.1** | Comparator v2 — diagnostics | ★★★ · 🔵 · 🔥 🔑 | §6.10.3: rank hypotheses, schedule ≤ 3 cheap diagnostic jobs (`source=diagnostic`), update evidence scores; seed-variance estimation via 3 seeds. | AC-3 fully (≥ 1 diagnostic run executed and reflected in the report) |
| **P7.2** | Notes & reports | ★★ · 🔵 | Scribe outputs (§6.11) — `plan.md` revisions, `log.md`, `results.md`, `lessons.md`; researcher notes via `/api/files/notes`; bundle export (zip); print stylesheet. | AC-20 (except view link, done in P10) |
| **P7.3** | Memory — lessons & Pokédex | ★★★ · 🔵 | Lesson writing with mandatory evidence links (§6.7), retrieval for context packs, `memory.hit` on dedup, Pokédex queries for the console. | Dedup answers < 300 ms (AC-12); lessons retrieved into a later project's context |
| **P7.4** | Discovery | ★★ · 🔵 · 🌐 | `papers/arxiv.py` (export API, Atom parse, cache), Scout ranking, Library entries with summaries (fast route). | AC-25 (online and from cache) |
| **P7.5** | Dataset & repo inputs | ★★★ · 🔵 | `data.inspect`, `repo.inspect` tools; `arena` kit consumption of a CSV (P11.5 provides the kit); `script_runner.py` regex-to-JSON shim for repos. | AC-24 for question + CSV + repo |
| **P7.6** | Author email drafts | ★ · 🔵 · 🔑 | `author_email` capability + template; draft saved, never sent. | Draft file for the grokking discrepancy |

---

## P8 — Frontend foundation & the console ★★★☆☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P8.1** | Net & store | ★★★ · 🔵 | `lib/labSocket.ts` (hello/since/resync/backoff/ping), `lib/api.ts`, generated contracts, `store/labStore.ts` pure reducers for every event kind used so far, `metricsStore` typed arrays; vitest with the P4.10 recorded session. | Replaying the slice session reproduces the brain's final state hash (projects/agents/jobs) |
| **P8.2** | Static export served by labd | ★★ · 🔵 | `next.config.ts` export settings; `just up` builds when stale; labd `ServeDir`; dev proxy for `next dev`. ⚠️ check Next 16 export docs. | `http://localhost:7700/` serves the app; `/m/` and `/replay/` resolve |
| **P8.3** | Layout & HUD | ★★ · 🔵 | Game/Split/Console modes (hotkeys 1/2/3), HUD (§9.7), Tailwind tokens reusing PokeStonks' palette and Press Start 2P / Atkinson fonts. | Modes switch without remounting the game |
| **P8.4** | Panels I | ★★★ · 🔵 | Quests (+ plan DAG, React Flow + dagre), Activity (virtualised, causal chain view), Experiments (uPlot with cones, run table, compare), Repro Report. | All four render the slice session and update live |
| **P8.5** | Panels II | ★★★ · 🔵 | Team (cards + lineage tree), Safari Map (heatmap canvas), Pokédex, Library (reader with highlighted spans), Notes (editor/preview), Compute, Lab Brain (reads `labml.json`), Policy. | Every panel renders from fixtures and live; no panel re-renders on metric frames (React profiler) |

---

## P9 — The game ★★★★☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P9.1** | Asset pipeline | ★★★ · 🔵 | `assets/build_atlases.py` (§9.6): GIF → strips + atlas JSON with durations; PMD `AnimData.xml` → atlas (row order, 1/60 s ticks, `CopyOf`); FireRed overworld humans → atlas (flipX for right); trainers; cries; `CREDITS.md` generated from PMD `credits.txt` + sources; `manifest.json` limited to the species in `roster.toml` + Eevee forms + gym Pokémon. | `/dev/art`-style page shows every species walking in 4 dirs and animating front/back |
| **P9.2** | Region map | ★★★ · 🔵 | Extend `maps.ts` Builder: region layout (§2.5) with towns (themes), routes, Lab/Center/Library/Day Care/PC buildings with warps, gyms, docks, Safari gate; collision; spawn points per station. | Ash walks the whole region; all warps work |
| **P9.3** | Lab interior | ★★★ · 🔵 | New interior builder (stations from §9.4.2), new procedural tiles (desk+PC, bookshelf, server rack, quest board, analysis table, Pokédex terminal) in `art/tileset.ts`; Oak NPC. | Stations exist with named target tiles |
| **P9.4** | Agent entities | ★★★ · 🔵 | `AgentEntity` (§9.4.1): grid-engine 2.45 add/remove at runtime, `moveTo(…, {algorithm:'A_STAR', noPathFoundStrategy:'CLOSEST_REACHABLE', pathBlockedStrategy:'WAIT'})`, animations driven manually from movement events (PMD 4-frame walks), animation states, nameplate, status ring, bubbles; capability → station mapping. | 12 agents path between stations at 60 fps |
| **P9.5** | The Director | ★★★★★ · 🟣 | `game/director/` per §9.5: per-entity FIFO, real-time bound & compression, global overlay queue, 2 s reconcile against `labStore`, spotlight rules, `Shift+E` event-id overlay; unit tests with synthetic lag. | Replaying the slice session at 4× speed never drifts from store truth; overlay shows seqs |
| **P9.6** | Gym scene | ★★★★ · 🔵 | Rewrite `BattleScene` → `GymScene`: leader + paper Pokémon vs runs (1–3), plates bound to budget/gap, turn synthesis from metric aggregates (§9.5), Oracle cone mini-chart, retreat on kill, badge on verdict; reuses `fx.ts`, `dialog.ts`, `plates.ts`. | A live grokking run plays as a battle with correct numbers in every dialog line |
| **P9.7** | Overlays & audio | ★★★ · 🔵 | Evolution, Catch (approval-gated), Day Care egg, Faint→PC; audio map + cries (§9.6). | Each overlay triggered by its fixture event only |
| **P9.8** | Binding audit | ★★ · 🔵 | Automated check: every AnimTask carries a `seq`; Playwright test asserts the overlay lists them; a "no backend" test (pause labd) → world goes idle within 2 s. | AC-21 |

---

## P10 — Remote compute & the phone ★★★☆☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P10.1** | Remote runner protocol | ★★ · 🔵 | `workers/remote/` common base: package kit + config into a self-contained script that prints JSON lines; labd spawns runners like jobs (§3.4.7). | Local "fake remote" runner passes the job contract tests |
| **P10.2** | Kaggle runner | ★★★ · 🔵 · 🔑 🔥(remote) | `kaggle kernels push -p <dir> --accelerator NvidiaTeslaT4` with a **fresh kernel slug per job** (⚠️ a reused slug kept a CPU image `[MEASURED]`), **live `kaggle kernels logs -f`** streaming of the JSON lines, status polling fallback, `kernels output` for artifacts, replay of JSON lines with original step order; datasets bundled or `enable_internet`. | AC-16 Kaggle half; overhead measured into the Router |
| **P10.3** | Colab runner | ★★★ · 🔵 · 🔑 🔥(remote) | `colab --auth oauth2 run --gpu T4 --timeout <budget_s> script.py` streaming stdout lines → labd (live!) — ⚠️ never omit `--timeout` (default 30 s); validate the GPU name; per-job `--config`; fallback `colab new/exec/download/stop`; session cleanup on kill. | AC-16 Colab half; session start overhead measured |
| **P10.4** | Pokégear PWA | ★★★ · 🔵 | `/m` (§9.8): pairing, inbox, projects, control, redirect text; PWA manifest; role `phone`. | AC-18 over LAN |
| **P10.5** | Voice redirect | ★★ · 🔵 · 🔑 | MediaRecorder → upload → Groq `whisper-large-v3` (custom UA) → `cmd.redirect`. | Spoken redirect revises a plan (AC-19 by voice) |
| **P10.6** | Tunnel & view links | ★★ · 🔵 · 🌐 | `just tunnel` (`cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:7700`), QR with the new HTTPS URL each start; `view` role links for collaborators. | Phone on 4G approves through the tunnel; view link is read-only |

---

## P11 — Multi-paper expansion ★★★★☆ 🔥 🧠

> Each paper = kit + paper pack + checklist + Oracle data + analyst + gym. Specs in Part 8.

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P11.1** | Distillation (Edge) | ★★★ · 🔵 · 🔥 🧠 | `kits/distill/` per §8.3 (teacher/student MNIST, full-batch GPU tensors, T/α sweep, omitted-class what-if), pack + checklist, `kd_darkknowledge` analyst, ≥ 40 library runs for the Oracle, gym (Lt. Surge). | Reproduced effect (distilled student closes most of the teacher–student gap) + what-if + report |
| **P11.2** | Tiny NeRF (3D) | ★★★★ · 🔵 · 🔥 🧠 | `kits/nerf/` per §8.4 (tiny_nerf_data.npz, PE L=6 vs L=0, bf16 autocast, spin-video render artifact), `nerf_spectrum` analyst, gym (Blaine) showing renders on the scoreboard. | PSNR trajectory matches §8.4 targets; no-PE what-if shows the gap; spin video plays in the UI |
| **P11.3** | Materials (Matbench) | ★★★ · 🔵 · 🧠 | `kits/materials/` per §8.5 (matbench_expt_gap & steels, RF on fractions/Magpie as the paper baseline, composition-attention model as the Roost-style what-if), CPU worker, `materials_parity` analyst, gym (Brock); Eevee→Vaporeon spawn story uses this domain. | MAE within tolerance of the published Matbench baseline + what-if + report |
| **P11.4** | Comparison arena | ★★★ · 🔵 · 🧠 | `kits/arena/` per §8.6 (trees vs MLP on tabular-benchmark subsets, equal budgets, 3 seeds) — also consumes user CSVs (AC-24). | Fair-comparison report with CIs |
| **P11.5** | Oracle/Navigator per kit | ★★★ · 🔵 · 🔥 🧠 | Library sweeps for the new kits, retrain, per-kit evaluation entries in `labml.json`. | Oracle AUROC reported per kit |
| **P11.6** | Four-gym run | ★★★ · 🔵 · 🔥 | Run all four reproduce projects end-to-end; record session `var/sessions/four_gyms.db`. | AC-4 |

---

## P12 — Hardening & rehearsal ★★★☆☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P12.1** | Doctor complete | ★★ · 🔵 | All §5.10 checks real; `just doctor` exit codes. | Green on the demo laptop |
| **P12.2** | Chaos drills | ★★★ · 🔵 | Scripts for: kill brain, kill worker, network off, 429 storm, disk low, unplug charger. | AC-23 |
| **P12.3** | Performance instrumentation | ★★★ · 🔵 | Event→screen latency probe (timestamp in `display`, measured in the client), frame-time stats, panel render counts. | AC-22 numbers into `var/reports/perf.json` |
| **P12.4** | Acceptance suite | ★★★ · 🔵 · 🔥 | `tests/acceptance/` AC-1…AC-25 (GPU where needed), single command `just acceptance`. | All green twice in a row |
| **P12.5** | README & credits | ★ · 🔵 | Architecture summary, how to run, every number from `var/reports`, licences (PokeAPI/Showdown sprites, PMD SpriteCollab CC BY-NC, PyMuPDF AGPL), limits. | README complete |
| **P12.6** | Rehearsals | ★★ · human · 🔥 | 3 full runs of §12.1 with a timer; record the best as `var/sessions/rehearsal_best.db` (REPLAY fallback); `llm-replay` cache populated; laptop prep (charger, performance mode, sleep off, notifications off, browser zoom, close RAM hogs). | 3 clean runs; fallback session plays |

---
