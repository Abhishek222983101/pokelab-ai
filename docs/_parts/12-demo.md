# PART 12 — DEMO & ACCEPTANCE

> Judging and pitch are the user's call; this part exists so the build has a concrete target. Every beat below is a *live* behaviour of the system, not a script the system follows.

## 12.1 The 6-minute storyboard (Split layout, plugged in, Performance mode)

| t | Beat | What happens (real) | PS |
|---|---|---|---|
| 0:00 | **The lab is alive** | Region map: agents asleep or working on a background exploration; HUD shows GPU, tokens, compute saved so far | D1, D25 |
| 0:20 | **The request** | Researcher types *"Reproduce Grokking (Power et al.) and tell me what happens without weight decay"* + drops the PDF | D2, D22 |
| 0:35 | **Oak thinks out loud** | Capability analysis on the quest board: read → spec → configure → run → analyse → compare; coverage bars; Pikachu selected (posterior card) and runs to the library desk; its real thoughts appear in bubbles | D5, D6, D26 |
| 1:10 | **Memory first** | Spec extracted with citations; the Pokédex recognises the base config → *"Found in the Pokédex: run job_… from yesterday"* — instant result, then Oak launches a **fresh seed** to show it live | D15 |
| 1:30 | **The Gym battle** | Sabrina (Power et al.) vs our run: our HP = budget, her HP = gap to 99 % test accuracy. Train acc saturates fast; test acc flat; the Oracle's cone widens… *"Oak's Pokédex senses something… grokking predicted in ~1,200 steps"* … then the jump: **"It's super effective!"** | D11, D16, D22 |
| 2:40 | **The what-if** | wd=0 + two Navigator-chosen neighbours run as a triple battle; wd=0's attacks keep missing; the Oracle calls it: **"Got away safely! Saved 41 GPU-s"**; the Safari map's fog lifts | D14, D19, D23 |
| 3:20 | **Why we differ** | Repro Report: paper ~10⁵ steps (Power) / ~10k epochs (Nanda) vs ours 19.8k; hypotheses with evidence — and a diagnostic 3-seed run it scheduled itself shows seed variance explains most of it | D13, D24 |
| 3:50 | **The team evolves** | A materials request arrives → skill gap → **"A wild EEVEE appeared!"** → the judge approves on *their* phone (QR) → Poké Ball → Eevee joins → later evolves into Vaporeon after its refined prompt beats v1 in shadow eval | D7, D9, D18 |
| 4:40 | **Darwin in the lab** | Team panel: lineage tree; a weak duplicate retires (faint → PC, reason shown); two redundant agents merge at the Day Care | D8, D10 |
| 5:10 | **Four gyms** | Region map: badges for Grokking, Distillation, NeRF (spinning rendered views), Materials — each with its own reproduced number and what-if | D12, D21 |
| 5:40 | **Honesty switch** | `Shift+E` shows event ids on every animation; Lab Brain panel: Oracle AUROC vs runs, compute saved, Medic tokens saved, Navigator vs grid | D16, D26, D27 |

**Fallbacks (labelled):** any beat can be shown from the recorded rehearsal session in REPLAY mode; any LLM step can be served from the cache in `llm-replay` mode.

## 12.2 The wow moments (each must work three times in a row in rehearsal)

1. **Grokking predicted before it happens** (Oracle precursor features) — then it happens.
2. **The judge approves a spawn from their own phone** and watches the Pokémon get caught.
3. **The Pokédex answers instantly** for a config it has seen; the Medic heals a known crash without any LLM call.
4. **The lab designs its own diagnostic experiment** to test why its result differs from the paper.
5. **Evolution with a number on it**: "v2 beat v1 by +0.12 mean reward on 4 replayed tasks".
6. **A NeRF render sharpening live**, and its spectrum showing why positional encoding matters.

## 12.3 Acceptance tests (the contract)

Each AC has a scripted check (`tests/acceptance/test_acN_*.py` or Playwright spec) that runs against a live lab (GPU) or REPLAY session as stated.

| AC | Requirement | Pass condition | PS |
|---|---|---|---|
| AC-1 | Grokking key result reproduced autonomously | A `reproduce` project on the Grokking paper completes with no human edits to code/config; the run shows train acc ≥ 0.99 well before test acc ≥ 0.95 (delayed generalisation), and test acc ≥ 0.95 within budget; badge awarded | D21, D22 |
| AC-2 | What-if wd=0 investigated | wd=0 run(s) do not reach 0.5 test acc within budget; ≥ 1 is early-stopped by the Oracle with `gpu_s_saved` recorded; result explained in the report | D14, D23 |
| AC-3 | Differences explained with evidence | Comparison report lists ≥ 2 hypotheses with evidence scores; ≥ 1 diagnostic run executed automatically; claim-guard passes | D13, D24 |
| AC-4 | Multi-domain | ≥ 3 papers from ≥ 3 PS domains each with: reproduced (or honestly partial) key result, ≥ 1 what-if, report | D12, D22 |
| AC-5 | Capability analysis | Every project emits `oak.capability_analysis` with reasons and coverage; visible on the quest board | D5 |
| AC-6 | Selection is learned | `oak.selection` events contain posteriors + model version; a replay simulation shows Selector cumulative reward > round-robin | D6, D16 |
| AC-7 | Spawn | A detected gap → `agent.spawn_proposed` → phone approval → `agent.spawned` with prior; the new agent completes a task | D7, D18 |
| AC-8 | Refine | An agent with recurring failures gets `agent.evolved` with shadow-eval evidence (or a recorded `refine_rejected` with evidence) | D9 |
| AC-9 | Merge | `agent.merged` with both parents archived and the child passing shadow eval | D10 |
| AC-10 | Retire | `agent.retired` with posterior evidence; its tasks re-assigned | D10 |
| AC-11 | Reward loop | Every completed task has `agent.rewarded` with Q/S/T/C/H; a 👎 from the researcher measurably lowers the agent's posterior mean | D8 |
| AC-12 | Memory dedup | Resubmitting a completed config returns `job.deduped` + `memory.hit` in < 300 ms | D15 |
| AC-13 | Failure repair | An injected known bug is fixed by the Medic with **zero** LLM calls in < 1 s triage; a novel bug is fixed by the Debugger with retrieved similar cases; the new fix is saved | D4, D11, D15 |
| AC-14 | Oracle | Live cones on running jobs; `var/reports/labml.json#oracle` shows AUROC ≥ 0.85 at 20 % prefix and ≤ 2 % wrong kills on held-out runs `[TARGET]` | D16 |
| AC-15 | Navigator | An `explore` project maps the wd × frac boundary; simulation report shows Navigator needs fewer runs than grid for boundary F1 ≥ 0.9 | D14, D19 |
| AC-16 | Remote compute | One job completes on Kaggle and one on Colab; metrics appear in the same Experiments panel | D3 |
| AC-17 | Environment handling | A kit/script missing a dependency is repaired by the Env Engineer (`uv` install from allowlist) and the fix is recorded | D4 |
| AC-18 | Mobile control | Phone pairs by QR; approve/reject/kill/redirect from the phone reflect on the desk in < 1 s | D18, D20 |
| AC-19 | Redirect | A running project redirected with a new instruction gets `project.plan_revised` (diff) and continues without restart | D20 |
| AC-20 | Notes & documents | Auto-written `plan/results/comparison/lessons.md`; researcher note edit persists; bundle export works; view-only link works; author-email draft generated | D17 |
| AC-21 | Interface binding & scale | Event-id overlay shows a seq for every playing animation; ≥ 6 agents + ≥ 3 runs + 2 projects on screen at ≥ 50 fps | D25–D27 |
| AC-22 | Fluidity | Scripted run of §12.1: no spinner > 2 s without real intermediate state; p95 event→screen < 150 ms (instrumented) | P2 |
| AC-23 | Resilience | Kill brain mid-project → resumed < 10 s with no lost events; kill a worker mid-run → Medic path; network off → cache/Groq/llm-replay keep the demo going | P6 |
| AC-24 | Non-paper inputs | A plain question (e.g. "does Grokfast speed up grokking?"), a CSV dataset and a repo path each become running experiments | D2 |
| AC-25 | Discovery | Scout finds related papers via arXiv (or cache) and adds them to the Library with summaries | D17 |

---
