# PokéLab — Gap Analysis (Problem Statement × Architecture × Build Plan × What Actually Runs)

Written 11 Oct 2026, after reading: `Elevate 1.0 PS list.pdf` (PS03, pp. 5–7), `Elevate-1.0-EventFlow.pdf`,
`docs/SYSTEM-ARCHITECTURE.md` (D1–D27, AC-1…25, Parts 2/6/7/8/9, Part 13 build plan), `docs/PROGRESS.md`,
`brain/pokelab_brain/acceptance.py`, and the code the demo actually executes.

> **How to read the status words.** The repo's own acceptance list says "14 real", but *real* there means
> "a unit/integration test of that module passes". It does **not** mean the demo loop calls the module.
> This document separates the two, so we never claim in front of a judge something the demo cannot show.

| Word | Meaning |
|---|---|
| ✅ **LIVE** | Happens in the running demo (typed request → Oak → agents → GPU → verdict); visible on `/lab/` |
| 🟡 **PARTIAL** | Works but narrower than the spec / rule-based stand-in / fixture on screen |
| 🔧 **BUILT, NOT WIRED** | Module + tests exist; the live project loop never calls it, so a judge cannot see it |
| ❌ **MISSING** | Not in the codebase |

Event timing (EventFlow): coding closed **Sun 08:00**; final judging **11:00–13:00**.

---

## 1. Verdict in one paragraph

The **spine is real and strong**: an event-sourced Rust core, a Python brain that runs Oak's loop, five real
paper-reproduction trainers on the laptop GPU, learned agent selection, a reward loop, human feedback, rule-based
evolution, crash recovery, and a live desk where everything on screen derives from logged events.
The **gap is breadth against PS03's second half**: PS03 asks the system to *go beyond reproduction* — run a
"what if?", investigate, **explain why results differ**, remember, repair, spawn/merge/retire agents, and expose
a large concurrent team. Most of those instruments were built and unit-tested in Phases 5–7 but were **never
connected to the project loop**, and the 2D world (Region/Gym scenes) was never connected to events at all.

---

## 2. PS03 demands D1–D27 — status against what a judge can see today

| ID | PS03 demand (short) | Status | Evidence / what is missing | Fix (effort) |
|---|---|---|---|---|
| D1 | Dynamic team of agents over the full ML lifecycle | 🟡 | 9 agents work a fixed 9-step `reproduce` template; no hypothesis/what-if/compare projects run live | what-if project (S–M) |
| D2 | Accepts a paper, question, algorithm, dataset, codebase or idea | 🟡 | Only the 5 named papers, typed as text (keyword match, LLM only as fallback). `tools/data.py`, `tools/repo.py`, `papers/discover.py` exist but are not wired. Only grokking's PDF is parsed (8 PDFs sit in `data/papers/`) | wire PDF/dataset intake (M) |
| D3 | Runs on local, Kaggle, Colab, remote | 🔧 | Remote runners tested against captured logs / one real Colab round trip; the live loop always runs local | route via `router/placement` (S) |
| D4 | Handles dependencies, env, data issues, impl errors, resources, hyperparameters | 🔧 | Medic (6 zero-LLM regex rules) and OOM guard exist; no Env-Engineer auto-install (AC-17 ❌); live loop only retries a failed step once | wire Medic into retry (S) |
| D5 | Meta-controller decides required capabilities | 🟡 | Template `reproduce.yaml` is loaded; `oak/capabilities.py` (LLM capability analysis) is **not called**, so no `oak.capability_analysis` event / quest-board reasons | call it, emit event (S) |
| D6 | Coordinates existing agents | 🟡 | Thompson Selector is real **but every capability has exactly one agent**, so it never chooses between alternatives — "selection" is vacuous today | add alternate agents per capability (S) |
| D7 | Spawns/adapts new specialised agents on a skill gap | 🔧 | `spawn.py` + `lifecycle_loop.py` work (tested with a real gap) but the 9 roster agents cover every capability, so no gap ever occurs; no approve-spawn UI path | ask for an uncovered capability → gap → spawn (M) |
| D8 | Reward loop: research outcome + compute cost + researcher feedback | 🟡 | Rewards and 👍/👎 are live and logged. **But** the scheduler passes constants (`latency_s=1.0`, `gpu_s=0.0`, quality = 1.0 if checks pass), so reward is ≈1.0 for everyone and levels saturate at 90–99 | feed measured wall-time/GPU-s/quality (S) |
| D9 | Consistently valuable agents are refined | 🟡 | **Rule-based promotion is live** (≥8 rewards, mean ≥0.90 → next species, evidence in event). The designed GEPA-lite refine + shadow-eval gate (`agents/refine.py`) is built, not wired | wire refine + shadow eval (M) |
| D10 | Poor agents merged / replaced / retired | 🔧 | `retire.py` evaluates after each task when the LLM router exists; `merge.py` only recommends; nothing triggers in a demo | scripted weak agent for demo (S) |
| D11 | Run experiments, observe, **diagnose failures, repair, improve** | 🟡 | Runs/observation live; diagnose/repair not shown (Medic unwired) | wire Medic (S) |
| D12 | **Compare multiple papers/approaches** under meaningful conditions | 🔧 | `workers/kits/arena` (tree vs MLP, paired t-test) runs on request; `compare` template + side-by-side UI not wired | comparison view (M) |
| D13 | **Determine why results differ** from reported findings | 🔧 | `science/comparator_v2.py` (17-item checklist + hypotheses, claim-guarded) built; diagnostic-job scheduling "not wired up yet" (PROGRESS P7.1); Repro tab shows one verdict row, no hypotheses | **wire comparator + diagnostic runs (M) — top priority** |
| D14 | **"What if?"** → investigate multiple possibilities automatically | ❌ live | `whatif.yaml` template validates; kit exposes `wd`, `frac`, `lr`, `beta2`, `seed`; **no what-if project ever runs**; Safari map is a fixture | **what-if sweep (M) — top priority** |
| D15 | Learnings persist and are reused | ❌ | `memory/pokedex.py` is a fix/lesson store, not a config-dedup index; **no `job.deduped` / `memory.hit` event exists** (AC-12 ❌). Resubmitting re-runs the GPU | config-hash dedup (S–M) |
| D16 | Gets better over time (what to try / how to execute / recover / next direction / which agent) | 🟡 | Selector posteriors persist from the event log (live). Oracle, Navigator, Medic, Router are trained/tested but not consulted by the loop; Oracle trained on 4 real curves (no AUROC computed, AC-14 ❌) | wire instruments (M each) |
| D17 | Workspace: discover/read papers, notes/Markdown, datasets/code, outputs, records, collaboration | 🟡 | `report.md` is written per project (live). Notes, discovery, author-email modules exist; **no Library / Notes / Pokédex panels** in the UI | panels (M) |
| D18 | Mobile remote control | 🟡 | `/m` pairs via code and can kill a job; Inbox (approve/reject), Projects and Redirect tabs are not built (AC-18 partial, AC-19 ❌) | phone inbox (M) |
| D19 | Multiple hypotheses simultaneously, chosen by evidence | 🔧 | Scheduler can run `max_parallel>1`; live runs `1` (so one agent is visible). Navigator not consulted | what-if sweep with 3 parallel runs (M) |
| D20 | Researcher can inspect, intervene, guide, approve, reject, redirect | 🟡 | Live: ask, 👍/👎, inspect, and the kill command exists on `/m`. Missing: approve/reject gates in the live loop, `project.plan_revised` redirect (AC-19 ❌), kill button on the desk | add kill + redirect (S–M) |
| D21 | Modest compute, meaningful evidence | ✅ | Grokking MLP groks in ~3 s on the RTX 5050; every kit runs on one laptop | — |
| D22 | ≥1 paper, key result reproduced **autonomously** | ✅ | Typed request → real run → test_acc 0.991 vs claim 0.95 → REPRODUCED + badge | — |
| D23 | ≥1 meaningful what-if extension | ❌ live | see D14 | **top priority** |
| D24 | Explain where and why results differ | ❌ live | see D13 | **top priority** |
| D25 | Organise a very large number of concurrent agents/activities/threads | 🟡 | 9 agents, one project at a time on screen; no filters/aggregation | filters (S) |
| D26 | UI shows what agents do, why, how they perform, how the team evolves | 🟡 | What/why/performance live (bubbles, WHY lines, levels). Team evolution: flash + feed row only — **no lineage tree** | lineage tree (S) |
| D27 | Controllable, not a notebook/chat | 🟡 | Desk + console + phone exist; the game is a live *display* — cannot walk Ash or click the world to command | Region scene (L) |

**Reading the table:** of the *deliverables* PS03 names (D22, D23, D24), only the first is demonstrable today.

---

## 3. Acceptance criteria AC-1…25 — repo status vs. demonstrable live

Repo `acceptance.py`: **14 real / 6 partial / 5 not implemented**. Re-judged for *what the demo shows*:

| AC | Requirement | Repo says | Live in demo? | Gap |
|---|---|---|---|---|
| AC-1 | Grokking reproduced autonomously | real | ✅ | — |
| AC-2 | What-if wd=0, Oracle early stop, `gpu_s_saved` | partial | ❌ | no what-if, no `gpu_s_saved` anywhere |
| AC-3 | Differences explained, ≥2 hypotheses, ≥1 diagnostic run | real | ❌ | comparator_v2 not called |
| AC-4 | ≥3 papers, ≥3 domains | real | 🟡 | 5 kits run real; only grokking re-verified end-to-end today |
| AC-5 | `oak.capability_analysis` event | real | ❌ | planner template only |
| AC-6 | Selection learned, beats round-robin | partial | 🟡 | posteriors logged; single-candidate caps (see D6) |
| AC-7 | Spawn with approval | real | 🔧 | works in test, never triggers live |
| AC-8 | Refine with shadow-eval evidence | real | 🟡 | rule-based promotion only |
| AC-9 / AC-10 | Merge / Retire | real | 🔧 | never triggers live |
| AC-11 | Reward Q/S/T/C/H; 👎 lowers posterior | real | 🟡 | breakdown logged; T/C are constants |
| AC-12 | Memory dedup <300 ms | not impl. | ❌ | — |
| AC-13 | Medic zero-LLM repair | partial | 🔧 | classifier exists, unwired |
| AC-14 | Oracle AUROC ≥0.85 | not impl. | ❌ | no AUROC; 4–5 curves |
| AC-15 | Navigator beats grid | not impl. | ❌ | 1-D knob only |
| AC-16 | Kaggle + Colab same panel | partial | ❌ | local only live |
| AC-17 | Env Engineer auto-repair | not impl. | ❌ | — |
| AC-18 | Mobile control <1 s | partial | 🟡 | pair + kill only |
| AC-19 | Redirect (`plan_revised`) | not impl. | ❌ | — |
| AC-20 | Notes & documents | real | 🔧 | report.md yes; no Notes UI |
| AC-21 | Binding & scale ≥50 fps | partial | 🟡 | binding structural; scale unproven |
| AC-22 | Fluidity p95 <150 ms | real | ✅ | measured p95 1–5 ms |
| AC-23 | Resilience (kill brain/worker) | real | ✅ | chaos drills; **note:** the ws keep-alive drop found today was a new class not covered by them (now fixed + tested) |
| AC-24 | Question / CSV / repo inputs | real | 🟡 | question only |
| AC-25 | Discovery via arXiv | real | 🔧 | `discover.py` unwired; arXiv rate-limited (test_discover fails externally) |

---

## 4. Architecture parts — coverage map

### 4.1 Backend (Parts 5–7)
| Component | Spec | Status |
|---|---|---|
| `labd` event store, hub, WS, replay, doctor, pairing | §5 | ✅ (+ `/api/telemetry`, request/feedback commands added today) |
| Job engine + warm pool | §5.5 | ✅ (job ids now unique across restarts; ws ping fix) |
| Brain bus, state fold, supervision | §3, §6.12 | ✅ (reconnect on dead socket fixed today) |
| LLM router (Elevate → Groq, cache, budgets) | §6.5 | ✅ built; live loop uses it only for intake fallback + lifecycle |
| Oak intake / planner / scheduler / verifiers | §6.2 | 🟡 fixed `reproduce` template; no `whatif` / `compare` / `explore` / `discover` projects run |
| Reward v2 | §6.9 | 🟡 constants for latency/GPU (see D8) |
| Lifecycle spawn/refine/merge/retire | §6.8 | 🔧 / 🟡 rule-based evolution live |
| Pokédex memory | §6.7 | ❌ dedup; 🔧 lessons store |
| ReproComparator v2 | §6.10 | 🔧 |
| Notes, author email | §6.11 | 🔧 |
| **ML instruments** Oracle 7.1 / Navigator 7.2 / Selector 7.3 / Medic 7.4 / Scout 7.5 / Router 7.7 / Analysts 7.8 | §7 | Selector ✅ live; Scout ✅ (gap detection live but never fires); Oracle 🔧 (4 curves, no AUROC); Navigator 🔧 (1-D); Medic 🔧; Router 🔧; Analysts 🔧 (grok signature on a real run) |
| Kits: grokking, distillation, NeRF, materials, arena | §8 | ✅ real trainers; each fetched/measured |
| Remote runners (Kaggle/Colab) | §8.8 | 🔧 |
| Env engineering | §8.9 | ❌ |

### 4.2 Frontend (Part 9 + GAME-DESIGN.md)
| Item | Spec | Status |
|---|---|---|
| Event-folded store, pure reducer, placement, binding audit | §9.2 | ✅ (60 tests) |
| **Lab desk `/lab`** (room scene, agent walkers, bubbles, HUD, panels, Ask-Oak) | — | ✅ the working demo surface (built in a separate session; wired to live data today) |
| `BootScene`/`PreloadScene` (PokeStonks fork, real atlases) | §9.3 | 🟡 built; hands off to a scene that doesn't exist |
| **`RegionScene`** (Ash walks the world, agents roam, warps) | §9.3 | ❌ maps/tiles/assets exist (campus, lab, 5 towns, 9 interiors, 22 reachability tests); scene not written. `/game/` now forwards to `/lab/` |
| **`GymScene`** (battle bound to `job.metric`) | §9.3, GD §5 | ❌ renderer forked, scene not written |
| Overlays: Evolution ✅ (white flash in room scene), Catch ❌, Day Care ❌, Faint ❌ | §9.3 | 🟡 |
| Director (queueing/compression) | §9.5 | 🟡 tested module; the room scene paces itself instead |
| Audio (music, SFX, cries) | §9.6 | 🟡 engine + toggles; not mapped to events on `/lab` beyond a few SFX |
| Console panels | §9.7 | HUD ✅ · Quests 🟡 (checklist, not DAG) · Activity ✅ · Team 🟡 (no lineage tree) · Experiments 🟡 (no Oracle cone / compare) · Safari 🟡 fixture · Repro 🟡 (no hypotheses) · **Pokédex ❌ · Library ❌ · Notes ❌ · Compute ❌ · Lab Brain ❌ · Policy ❌** |
| Phone `/m` | §9.8 | 🟡 pair + kill; Inbox/Projects/Redirect ❌ |

### 4.3 Binding table (§2.7) — which visuals have a real event behind them
| On screen | Event | Emitted by the live brain? |
|---|---|---|
| Walk to station | `agent.task_started` | ✅ |
| Thought bubble text | `agent.thought` | ✅ (added today; text built from real results) |
| "…" thinking bubble | `llm.call_started` | ❌ (no LLM in the loop) |
| Hurt + "!" | `agent.task_failed` | 🟡 only when a check fails |
| XP / level-up | `agent.rewarded` | ✅ |
| Evolution animation | `agent.evolved` | 🟡 rule-based (spec: only after shadow eval) |
| Wild Pokémon at the door | `agent.spawn_proposed` | ❌ |
| Egg / Day Care | `agent.merged` | ❌ |
| Faint → PC | `agent.retired` | ❌ never fires in demo |
| Gym damage / "super effective" | `job.metric` | ✅ events exist; **no Gym scene to draw them** (the Experiments chart shows them) |
| "Got away safely!" | `job.killed{oracle_early_stop}` | ❌ |
| Badge | `project.badge_awarded` | ✅ |
| Pokédex glow | `memory.hit` | ❌ |
| Safari fog lifts | `ml.navigator_updated` | ❌ |
| Boat to Kaggle | `compute.route_decided` | ❌ |

---

## 5. Build plan Part 13 — claimed status vs reality

| Phase | PROGRESS.md says | Reality check |
|---|---|---|
| P0 foundations | ✅ | ✅ |
| P1 labd | ✅ | ✅ — plus 2 bugs found today (non-text frame hang-up; job-id reuse) that its tests did not cover |
| P2 workers / grokking | ✅ | ✅ |
| P3 brain foundation | ✅ | ✅ (one dead-socket bug fixed today) |
| P4 agents & Oak vertical slice | ✅ | 🟡 it was proven through a *test*; the running brain did not execute Oak's loop until today (runtime built this session) |
| P5 ML instruments | 🟡/✅ | 🔧 built + unit-tested; Oracle/Navigator trained on 4–5 runs; **none consulted by the live loop** |
| P6 lifecycle | ✅ | 🔧 proven in simulation; rule-based evolution live from today |
| P7 science & workspace | ✅ | 🔧 modules exist; comparator diagnostics "not wired" (own note) |
| P8 frontend foundation & console | ✅ | 🟡 old `/console`; new `/lab` desk is the real surface |
| **P9 the game** | ✅ | ❌ **reopened** — Region/Gym not connected; the old P9 was a text-label approximation (this is what you rejected) |
| P10 remote & phone | ✅ | 🟡 |
| P11 multi-paper | ✅ | ✅ trainers; ✅ real runs; UI shows one paper's chart at a time |
| P12 hardening | ✅ (12.6 rehearsal human) | 🟡 chaos drills real; rehearsal not done |

**Root cause of the pattern:** phases were closed on *module tests*, with no "wired into the live loop" gate.
Add that gate to the Definition of Done: *"a judge can see it happen after typing one request."*

---

## 6. Frontend ↔ backend seams that cause small bugs

| # | Seam | Symptom a user saw | Status |
|---|---|---|---|
| 1 | labd closed the brain socket on any non-text frame (client keep-alive ping) | Agents "not working": brain dropped ~20 s after start, then silently idle | ✅ fixed + regression test |
| 2 | Brain never noticed a dead socket (reader ended, subscriber waited forever) | Requests queue; nothing reacts | ✅ fixed (`subscribe` raises → reconnect) |
| 3 | Job ids restarted at `job-1` each labd boot; brain correlates `job.done` by id | A step "finished" instantly with a stale result | ✅ fixed |
| 4 | Steps completed in ms | Agents appeared asleep; nothing visible | ✅ one agent at a time, ≥2.5 s dwell, real thought bubbles |
| 5 | Interrupted projects are never resumed or closed after a restart | A quest sits at "44% running" forever | ❌ open — close or resume on boot |
| 6 | Double-clicking Ask creates duplicate projects; queue not shown | 6 identical quests | ❌ open — dedupe + "queued" state |
| 7 | Reward uses constants for latency/GPU | Every level saturates ~90–99 | ❌ open |
| 8 | One agent per capability | Selector "choice" shows a single candidate | ❌ open |
| 9 | Preload hands off to a nonexistent `Region` scene | `/game/` blue screen | ✅ worked around (forward to `/lab/`); real fix = write the scene |
| 10 | Navigator/Safari not streamed | Safari tab is a labelled fixture | ❌ open |
| 11 | HUD "JOBS" = started without done | Can stay >0 after a crash | 🟡 minor |

---

## 7. Technology & method inventory (what is actually used)

- **Event sourcing**: SQLite (WAL) single-writer log (`labd`, Rust: axum, rusqlite, tokio); every UI/agent state is a *fold* of events; replay + `since` resume; golden-fixture contracts across Rust/Python/TS.
- **Compute**: warm Python worker pool over JSON-lines stdin/stdout; per-kit device selection; GPU telemetry via `nvidia-smi`.
- **Agent selection**: Beta–Bernoulli **Thompson sampling** per agent (`labml/selector`); posterior mean ×100 = displayed level.
- **Reward**: weighted quality / success / timeliness / cost / human-feedback (`reward_v2`).
- **Planning**: YAML plan templates (reproduce, whatif, compare, explore, discover) validated as a DAG; verifier checks (`job_completed`, `metric_present`, `metric_threshold`, `config_validates`, …) — code-only.
- **ML instruments (built)**: GBM/logistic **Oracle** on curve features; Gaussian-process + **UCB** **Navigator**; regex **Medic** (zero-LLM); coverage-based **Scout**; rule-based **Compute Router**; FFT-based grokking **analyst** (embedding Fourier concentration).
- **Kits (real papers)**: grokking (Nanda/Power; modular addition MLP/transformer), distillation (Hinton; MNIST), tiny NeRF (Mildenhall; lego), Matbench-style materials (superconductor Tc; gradient boosting), tree-vs-MLP arena (Grinsztajn; paired t-test).
- **LLMs**: Elevate gateway then Groq (fallback, cache, rate limits, daily budget) — used for intake fallback, capability/lifecycle drafting; **not** on the reproduce path.
- **Frontend**: Next.js static export, Phaser 3 + grid-engine, zustand + pure reducer, PokeStonks-style tokens/audio.

---

## 8. Prioritised fix plan

Ordered by *judge-visible PS03 value per hour*. Effort: S ≈ 30–60 min, M ≈ 2–3 h, L ≈ half a day+.

| # | Fix | Closes | Effort | Notes |
|---|---|---|---|---|
| 1 | **What-if + explain-why project** — "what if weight decay is 0?" runs baseline + 2–3 variants of the grokking kit (`wd`, `frac`), comparator_v2 builds the evidence table, Repro tab shows hypotheses with scores | D13 D14 D19 D23 D24, AC-2/3 | M | single biggest gap; kit already exposes the knobs |
| 2 | **Real reward inputs + alternate agents** (measured wall-time/GPU-s; a second agent for ≥3 capabilities) so Selector truly chooses and levels diverge | D6 D8 D16, AC-6/11 | S | makes "learning" defensible |
| 3 | **Pokédex dedup** — same kit+config hash → `job.deduped` + `memory.hit`, UI glow | D15, AC-12 | S–M | repeat request returns instantly |
| 4 | **Oracle early-stop + `gpu_s_saved`** on the what-if sweep; `job.killed{oracle_early_stop}` | D16 D19, AC-2/14 | M | needs richer curves; honest labelling if the model is weak |
| 5 | **Close/resume interrupted projects; dedupe requests; show queue** | seams #5 #6 | S | removes ghost quests |
| 6 | **Paper viewer panel** — the real PDF chunks with claim spans highlighted as Pikachu reads | D17, AC-20/24 | M | the "visual demo of a paper" you asked for |
| 7 | Spawn demo: request an uncovered capability → Eevee proposal → approve on desk/phone → joins | D7, AC-7 | M | |
| 8 | Medic into the retry path (OOM → halve batch; show triage) | D4 D11, AC-13 | S–M | |
| 9 | Lineage tree + Team evolution panel | D9 D26 | S–M | |
| 10 | **RegionScene + GymScene** (the PokeStonks-style world, Ash, gym battle from `job.metric`) | D27, P9 | L | do last; `/lab` already carries the demo |
| 11 | Kaggle/Colab routed job (labelled "remote") | D3, AC-16 | M | needs network/credentials at demo time |
| 12 | Phone Inbox / Redirect (`project.plan_revised`) | D18 D20, AC-18/19 | M | |

---

## 9. What we can honestly say today (and must not)

**Say:** five real papers reproduce on a laptop GPU with measured verdicts; agents are picked by a learned bandit
and rewarded; researcher feedback changes posteriors; agents promote along evolution lines by a stated rule; every
animation and number traces to a logged event (Shift+E); the system survives process kills (chaos drills) and
reconnects.

**Do not say:** that agents write code from a paper (they run our implementations of five papers); that the system
runs what-if studies, explains differences, remembers configs, spawns/merges/retires agents, or runs on Kaggle/Colab
**live** (all built or partly built, none shown today); that the Pokémon world is playable.
