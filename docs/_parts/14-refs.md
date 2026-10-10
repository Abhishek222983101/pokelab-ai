# PART 14 — RISKS, DECISIONS, REFERENCES

## 14.1 Risk register

| # | Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|---|
| R1 | Elevate gateway rate limits (~10 rapid calls → 429/60 s) stall agents | High | High | Adaptive buckets, priority queue, Groq overflow, cache, ≤ 6-step tasks, ingestion pre-cached (§6.5) |
| R2 | Elevate has no tool-calling / schema enforcement | Certain `[MEASURED]` | High | Text action protocol + repair + validation (§6.3.2–6.3.3) |
| R3 | Venue network blocks or crawls (Fortinet, 1.6 s RTT) | High | High | Offline-first assets, LLM cache, `llm-replay`, REPLAY sessions, hotspot plan (§11.3) |
| R4 | Laptop on battery → runs 3–3.5× slower | Medium | High | Power guard banner; rehearsal checklist; hero run sized for AC (§5.7) |
| R5 | Host RAM exhaustion (15 GB; warm worker 1.17 GB each; browser) | Medium | High | 2 GPU workers max; CPU worker without torch; recycle at 3 GB RSS; doctor RAM check; close tabs |
| R6 | Disk full (36 GB free) | Medium | Medium | One venv; datasets ≤ 2 GB; checkpoints log-spaced & pruned; doctor disk check |
| R7 | LLM writes broken code during the demo | Medium | Medium | Kits are verified implementations the agents configure; agent-written code runs as isolated script jobs; Medic + Debugger loop; `llm-replay` for rehearsed prompts |
| R8 | Oracle kills a run that would have succeeded | Low | High | Operating point ≤ 2 % wrong kills on held-out data; never auto-kill the hero reproduction; 5 s human veto |
| R9 | Lifecycle oscillation (spawn/retire churn) | Low | Medium | Min-task thresholds, discounting, simulation test P6.6 |
| R10 | Paper pack extraction errors | Medium | Medium | Human review + `pack_corrected` events; ground truth tables in Part 8 |
| R11 | Phaser/Director drift from truth under load | Medium | Medium | 2 s reconcile + compression rules + replay tests at 4× speed (P9.5) |
| R12 | Kaggle reuses a CPU image on an existing kernel slug | Happened `[MEASURED]` | Low | Fresh slug per job + explicit `--accelerator NvidiaTeslaT4` (P10.2) |
| R13 | Groq rejects default User-Agent (403/1010) | Happened `[MEASURED]` | Low | Custom UA everywhere (§4.3.2) |
| R14 | Elevate key is shared across the team and quota-limited (800 k/day) | Certain | Medium | Budget ledger, 95 % hard stop, fresh quota at 05:30 IST (before judging) |
| R15 | Static export restrictions in Next 16 | Low | Medium | Only 3 static routes, no server features; read the bundled docs (P8.2) |
| R16 | Asset licences | Low (local hackathon) | Low | `CREDITS.md` (PMD CC BY-NC per-sprite credits, © TPC art, Showdown artists); vendor assets git-ignored |
| R17 | `NODE_TLS_REJECT_UNAUTHORIZED=0` in the shell profiles disables TLS checks for all Node processes | Present `[MEASURED]` | Medium | Remove in P0.4 with the user's OK |
| R18 | Colab CLI `--timeout` defaults to 30 s → long jobs die | Certain if omitted | Medium | Always pass `--timeout` (P10.3) |
| R19 | Groq limits are per organisation (8 k tok/min) — big prompts don't fit | Certain | Medium | Compact prompt variant for Groq (§6.5.3) |
| R20 | Quick-tunnel hostname changes on every restart; QUIC blocked | Certain | Low | `--protocol http2`; re-show QR; LAN/hotspot first |
| R21 | Accidental Phaser/grid-engine upgrade breaks the game | Medium | High | Exact pins (3.80.1 / 2.45.0); Phaser 4 migration only after the event |

## 14.2 Decision log

| # | Decision | Section | Status |
|---|---|---|---|
| D-01 | labd is the single writer of `lab.db` | §3.2 | frozen |
| D-02 | Web is a static export served by labd | §3.2, §9.1 | frozen |
| D-03 | Event sourcing; projections rebuildable | §3.2 | frozen |
| D-04 | Rust core / Python intelligence+compute / TS presentation | §4.1 | frozen |
| D-05 | Agents are data executed by one generic runtime | §6.4 | frozen |
| D-06 | Own text action protocol (no native tool-calling) | §6.3.2 | frozen (measured) |
| D-07 | Warm pool for kits, fresh process for agent scripts | §5.5.3, §8.1 | frozen |
| D-08 | Small ML models for numbers/statistics/routing; LLMs for language/code | Part 7 | frozen |
| D-09 | One JSON-lines protocol for local/Kaggle/Colab | §8.8 | frozen |
| D-10 | Pydantic → JSON Schema → TS; Rust mirrors + fixtures | §10.1 | frozen |
| D-11 | Offline-first everything | §11.3 | frozen |
| D-12 | JSON over WS/HTTP + JSON lines; no broker, no Docker | §4.1 | frozen |
| D-13 | Paper choice: Grokking hero + Distillation + tiny NeRF + Matbench (+ comparison arena) | Part 8 | frozen after P11 benchmarks confirm |
| D-14 | Ash = researcher, Oak = meta-controller, battles = experiments with HP = budget/gap | Part 2 | frozen |
| D-15 | Real Pokémon sprites (user decision; local hackathon) | §2.4, §9.6 | frozen |
| D-16 | ≤ 2 concurrent GPU jobs; hero run alone | §5.5.1 | frozen (measured) |
| D-17 | Earlier "no ML in the orchestrator" ruling is replaced by Part 7: *no custom model replaces the LLM*; small learned models do what LLMs can't | §7.0 | frozen |
| D-18 | Versions as verified in §4.3 (Next 16.3.8, Phaser 3.80.1 + grid-engine 2.45.0 exact, axum 0.8.9, rusqlite 0.40.2, openai 3.28, websockets 17.2, fastembed 0.9) | §4.3 | frozen for the event |

## 14.3 Open questions (owner: user)

1. **W&B API key** (needed before P2.6).
2. GitHub remote: create `pokelab` repo (private?) and push after P0?
3. Final product name (working name "PokéLab").
4. Portal PS code — EL02 or other (check dashboard).
5. Keep a second hero option ready (e.g. Lottery Ticket) if a P11 paper fails its reproduction target?

## 14.4 Glossary

| Term | Meaning here |
|---|---|
| **Agent** | An `AgentSpec` row executed by the generic runtime; shown as a Pokémon |
| **Capability** | A tag from the taxonomy (§6.4.1) a task requires and an agent offers |
| **Kit** | A verified, configurable experiment implementation in `workers/kits/` |
| **Job** | One execution of a kit/script (local or remote) |
| **Project** | A research request with its plan, jobs, reports |
| **PaperPack** | Machine-readable paper: claims, spec, unspecified details, pitfalls |
| **Oracle / Navigator / Selector / Medic / Scout / Router / Analysts** | The labml instruments (Part 7) |
| **Curve library** | All metric histories of all runs; the Oracle's training data |
| **Bug Gym** | Fault-injection runs that seed the Medic |
| **Shadow evaluation** | Replaying recorded tasks against a candidate agent version before promotion |
| **Director** | The frontend engine that turns events into animations honestly |
| **Grokking** | Delayed generalisation: train accuracy saturates long before test accuracy jumps |
| **LTTB** | Largest-Triangle-Three-Buckets downsampling for charts |
| **Thompson sampling** | Choose by sampling from each option's posterior; balances exploration/exploitation |
| **Straddle / LSE** | Acquisition that seeks points whose class (e.g. grok / no-grok) is most uncertain |
| **REPLAY mode** | Serving a recorded event log, clearly labelled, as a fallback |

## 14.5 Local paths (everything an agent needs to find)

| What | Path |
|---|---|
| This project | `~/elevate-ps03/` (docs in `docs/`, assets in `assets/vendor/`, datasets in `data/raw/`) |
| PS list / event flow / portal guide | `~/Downloads/Telegram Desktop/{Elevate 1.0 PS list.pdf, Elevate-1.0-EventFlow.pdf, Elevate Participant Portal Guide.pdf}` |
| Concept docs | `~/Downloads/gamified_multi_agent_system_architecture (1).md` (canonical), `~/Downloads/abhishek ka prompt.docx` |
| Previous handoff | `~/elevate-ps03-handoff.md` |
| PokeStonks (engine source) | `~/PokeStonks` (branch `feat/v4-integration`; web app `apps/web`; 80 tests pass) — github.com/Abhishek222983101/pokestonks |
| PokeStonks architecture doc (format reference) | `~/monad v4 blitz/PokeStonks-ARCH-V4.md` |
| SatyaCheck blueprint (format reference) | `~/Documents/sys archs/SATYACHECK_BLUEPRINT.md` |
| Showdown sprite mirror (Gen 1–2 × 6 styles, 1 500 trainers, 159 fx) | `~/elevate-ps03/assets/vendor/showdown/` |
| Datasets fetched 10 Oct | `~/elevate-ps03/data/raw/{mnist, tiny_nerf, matbench_expt_gap, matbench_steels}/` |
| Benchmark scripts, logs, probe tools (copied from /tmp on 10 Oct) | `~/elevate-ps03/scripts/reference/{grokbench, kitbench, tools, papers}` — `grokbench/grok.py` is the seed of the grokking kit; `kitbench/{kd_mnist,tiny_nerf,materials_rf,warm_worker,concurrency}.py` seed the other kits |
| Grokking-literature PDFs (8 papers) | `~/elevate-ps03/data/papers/*.pdf` (text versions in `scripts/reference/papers/`) |
| Reference outputs | `~/elevate-ps03/data/reference_outputs/{nerf_L6_spiral_frames.npy, kd_teacher30.pt}` |
| Graft code graph of PokeStonks | scratchpad `graft-pokestonks/` (regenerate with `graft build --dir <out> ~/PokeStonks`) |
| Exa CLI | `~/bin/exa` (key `~/.config/exa/key`) |
| Kaggle / Colab CLIs | `~/.local/bin/kaggle`, `~/.local/bin/colab` (both logged in) |

## 14.6 References

**Problem & event**
- Elevate 1.0 portal — https://elevate1-0.vercel.app/portal (LLM gateway `https://elevate1-0.vercel.app/api/ai`)

**Prior art (agents & research automation)**
- Agent Laboratory — https://agentlaboratory.github.io/ · arXiv 2501.04227 · https://github.com/SamuelSchmidgall/AgentLaboratory (MIT)
- AgentRxiv — arXiv 2503.18102
- AI Scientist v2 — https://github.com/SakanaAI/AI-Scientist-v2 · arXiv 2504.08066
- AIDE — https://github.com/WecoAI/aideml (MIT)
- ADAS / Meta Agent Search — arXiv 2408.08435 · AFlow — arXiv 2410.10762 · MaAS — arXiv 2502.04180 · EvoAgent — arXiv 2406.14228 · EvoMAC — arXiv 2410.16946 · MetaAgent — arXiv 2507.22606 · AgentFactory — arXiv 2603.18000 · Agent KB — arXiv 2507.06229
- Darwin Gödel Machine — arXiv 2505.22954 · ShinkaEvolve — arXiv 2509.19349 · AB-MCTS / TreeQuest — arXiv 2503.04412
- Who&When failure attribution — arXiv 2505.00212 · Self-evolving agents survey — arXiv 2507.21046
- GEPA — arXiv 2507.19457 (`pip install gepa`) · OPRO — arXiv 2309.03409
- MLE-bench — https://github.com/openai/mle-bench · PaperBench — arXiv 2504.01848
- RouteLLM — arXiv 2406.18665 · LinUCB — arXiv 1003.0146

**Grokking & ML-layer grounding**
- Power et al. 2022 — arXiv 2201.02177 · Nanda et al. 2023 — arXiv 2301.05217 · Omnigrok — arXiv 2210.01117 · Grokfast — arXiv 2405.20233 (https://github.com/ironjr/grokfast) · Prieto et al. (softmax collapse) — arXiv 2501.04697 · Thilak et al. (slingshot) — arXiv 2206.04817 · Kumar et al. (lazy→rich) — arXiv 2310.06110 · Notsawo et al. (predicting grokking) — arXiv 2306.13253
- LC-PFN — arXiv 2310.20447 · Optuna TPE — arXiv 1907.10902 · Straddle/LSE — Bryan et al. (NeurIPS 2005); Gotovos et al. (IJCAI 2013)

**Papers for the other gyms** — see Part 8 (each with links and verified numbers)

**Tools & assets**
- PyTorch cu130 wheels — https://download.pytorch.org/whl/cu130
- Google Colab CLI — https://github.com/googlecolab/google-colab-cli · Colab MCP — https://developers.googleblog.com/announcing-the-colab-mcp-server-connect-any-ai-agent-to-google-colab/
- Kaggle CLI — https://github.com/Kaggle/kaggle-api
- Exa MCP — https://exa.ai/docs/reference/exa-mcp
- PMD SpriteCollab — https://github.com/PMDCollab/SpriteCollab · PokeAPI sprites — https://github.com/PokeAPI/sprites · PokeAPI cries — https://github.com/PokeAPI/cries · Pokémon Showdown sprites — https://play.pokemonshowdown.com/sprites/
- grid-engine — https://github.com/Annoraaq/grid-engine · Phaser 3 — https://phaser.io · uPlot — https://github.com/leeoniya/uPlot · React Flow — https://reactflow.dev
- fastembed — https://github.com/qdrant/fastembed · PyMuPDF4LLM — https://pymupdf.readthedocs.io/en/latest/pymupdf4llm/

---

*End of the blueprint. Start at P0.1. Keep `docs/PROGRESS.md` honest.*
