# PART 13 — THE BUILD PLAN

## 13.0 Read this first

### 13.0.1 How the plan is ordered

Phases are ordered by **dependency first, difficulty second**: the hardest, riskiest work (the core, the agent loop, the ML layer) is done *early*, as soon as the things it stands on exist — never late. Every phase ends in a **runnable, tested state**; nothing is "wired up later". A **vertical slice** exists at the end of P4: one research request → autonomous grokking reproduction → report, with no game yet (backend demo-able on its own). Everything after P4 deepens or presents a system that already works.

```
P0 ─► P1 ─► P2 ─► P3 ─► P4 ═══ VERTICAL SLICE ═══► P5 ─► P6 ─► P7
                          │                         │
                          └────► P8 ─► P9 ──────────┴──► P10 ─► P11 ─► P12
```
(P8/P9 may start once P1 + the P4 event fixtures exist; when one builder works sequentially, follow the numbers.)

### 13.0.2 Difficulty ranking & machine needs

| Rank | Phase | Difficulty | Why it is hard | 🔥 GPU / Performance mode | 🧠 ML | 🔑 APIs |
|---|---|---|---|---|---|---|
| 1 | **P4** Agents & Oak — vertical slice | ★★★★★ | LLM non-determinism, protocol robustness, autonomous end-to-end correctness | P4.10 | — | Elevate, Groq |
| 2 | **P5** The ML layer | ★★★★★ | Correct features/labels, honest evaluation, no leakage, GPU sweeps | **P5.1, P5.2, P5.4** | **all** | W&B |
| 3 | **P1** `labd` core | ★★★★☆ | concurrency, process trees, durability, backpressure | — | — | — |
| 4 | **P3** Brain foundation & LLM router | ★★★★☆ | rate limits, fallbacks, caching, crash-safe state | — | — | Elevate, Groq |
| 5 | **P6** Lifecycle & evolution | ★★★★☆ | shadow evaluation, statistics, approvals | P6.3 (light) | partly | Elevate |
| 6 | **P9** The game | ★★★★☆ | volume of scene work, Director timing, asset pipeline | — | — | — |
| 7 | **P11** Multi-paper expansion | ★★★★☆ | four mini research projects | **all** | **all** | W&B |
| 8 | **P2** Workers & grokking kit | ★★★☆☆ | protocol discipline, telemetry correctness | **P2.4–P2.6** | P2.5 | W&B |
| 9 | **P7** Science & workspace | ★★★☆☆ | evidence discipline, many small features | P7.2 (light) | — | Elevate |
| 10 | **P8** Frontend foundation & console | ★★★☆☆ | stripping PokeStonks cleanly, fast charts | — | — | — |
| 11 | **P10** Remote compute & mobile | ★★★☆☆ | external CLIs, pairing, networks | P10.2–P10.3 (remote GPUs) | — | Kaggle, Colab, Groq (Whisper) |
| 12 | **P12** Hardening & rehearsal | ★★★☆☆ | discipline, not complexity | **P12.4–P12.6** | — | all |
| 13 | **P0** Foundations | ★★☆☆☆ | — | — | — | — |

🔥 = **plug in the charger, `powerprofilesctl set performance`, fans on, close the browser tabs you don't need** (RAM is the real limit: each warm GPU worker idles at 1.17 GB `[MEASURED]`).

### 13.0.3 Which Claude model runs which sub-phase

| Marker | Model | Use for |
|---|---|---|
| 🔵 | **Sonnet 5** (default) | ~80 % of sub-phases: implementation against an explicit spec in this document |
| 🟣 | **Opus 5.5** | Where a subtle error silently ruins the system: the job engine's process/kill semantics (P1.4), the LLM router (P3.3), the agent runtime & protocol (P4.4), the scheduler (P4.7), Oracle & Navigator modelling and evaluation (P5.2, P5.3), shadow evaluation (P6.3), the Director (P9.5) — and any "the metric looks too good/too bad" leakage hunt |

### 13.0.4 Accounts & keys checklist

| Need | Status (10 Oct) | Where it goes |
|---|---|---|
| Elevate team key | ✅ have (strip the `HideCopy` suffix) | `.env ELEVATE_TEAM_API_KEY` |
| Groq keys ×2 | ✅ have | `.env GROQ_API_KEY_1/2` |
| Kaggle | ✅ OAuth logged in (`abhishektiwari2112`), T4 verified | CLI store |
| Colab | ✅ CLI logged in, T4 verified | CLI store |
| **Weights & Biases** | ❌ **needed from the user** before P2.6 | `.env WANDB_API_KEY` (or `wandb login`) |
| Exa | ✅ (dev-time research only, `~/bin/exa`, MCP) | `~/.config/exa/key` |
| GitHub remote | user's decision | — |

### 13.0.5 Standing rules for every sub-phase

1. **Start** by reading: this sub-phase's row, the sections it cites, `docs/PROGRESS.md`, `git log --oneline -15`. Never "read the whole blueprint".
2. **Never redesign** what a section decides; cite it. To change a `[DECISION]`, write `docs/decisions/NNN-title.md` with the reason and update §14.2.
3. **Done means:** the "Done when" check passes **and** the tests for that component pass (`just test` subset) **and** a commit `P4.4: agent runtime + protocol` **and** one line in `PROGRESS.md` (✅/🟡/❌ + the key number).
4. **Long jobs run detached** (`nohup … > var/logs/X.log 2>&1 &` or the harness's background mode); check with `tail -n 30`, never `cat` whole logs.
5. **No number reaches the UI or a slide unless it comes from `var/reports/*.json`.**
6. **Fixtures before UI:** every new event kind gets a fixture in `contracts/fixtures/` and a recorded example stream for the frontend.
7. **Secrets** never in code, commits, logs or screenshots.
8. **Next.js code:** read `web/node_modules/next/dist/docs/` for anything you are unsure about (Next 16 differs from training data).

### 13.0.6 Session starter template (paste into a fresh Claude Code session)

```
Project: PokéLab (Elevate 1.0 · PS03). Blueprint: docs/SYSTEM-ARCHITECTURE.md (+ docs/OVERVIEW.md).
Current sub-phase: P4.4 — Agent runtime + action protocol (see its row in Part 13 and §6.3, §6.4.3, §10.2).
Relevant files: brain/pokelab_brain/agents/{runtime.py,protocol.py,context.py}; tests in brain/tests/test_protocol.py.
Contracts: contracts/pokelab_contracts/{agents.py,events.py}. Do not modify other phases' files.
Constraints: Elevate gateway has NO native tool-calling (use the text protocol §6.3.2); prompts ≤ 6k tokens.
Done when: (copy the "Done when" cell). Then commit "P4.4: …" and add a PROGRESS.md line.
```

---

## P0 — Foundations ★★☆☆☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P0.1** | Repo & workspace skeleton | ★ · 🔵 | `git init` in `~/elevate-ps03`; create the tree of §4.4 (empty packages with `__init__.py`, `Cargo.toml` workspace with the 6 crates, `pyproject.toml` uv workspace with members `contracts`, `brain`, `labml`, `workers`); `.gitignore` (§4.4); `justfile` with the targets of §4.6 (stubs allowed); `docs/PROGRESS.md` listing every sub-phase id of Part 13; move these docs into `docs/`. | `just --list` shows all targets; `cargo check` and `uv sync` succeed on the empty skeleton |
| **P0.2** | Python env | ★ · 🔵 · 🌐 | `uv python install 3.12`; `uv venv -p 3.12 .venv`; deps of §4.3.2; **torch 2.14.1 + torchvision** (the default PyPI wheel is the cu130 build with sm_120 — verified; the `download.pytorch.org/whl/cu130` index also works). One venv for everything (36 GB disk free!). | `python -c "import torch;print(torch.cuda.get_device_name(0), torch.cuda.get_arch_list())"` lists `sm_120`; `import fastembed, sklearn, pymupdf4llm, wandb` OK |
| **P0.3** | Node & web fork | ★ · 🔵 | Copy `~/PokeStonks/apps/web` → `web/` (no `.git`, no `node_modules`); standalone `package.json` (drop workspace deps `game-core`, `contracts-abi`); remove the web3/globe files of §9.1 (delete imports until `pnpm build` compiles); bump `next`/`eslint-config-next` to **16.3.8**; pin `phaser` 3.80.1 and `grid-engine` 2.45.0 exactly; keep `typescript ^5`; add `uplot@1.6.32`, `@xyflow/react@12.12.0`, `@dagrejs/dagre@3.1.1`, `react-markdown`, `remark-gfm`, `qrcode.react@4.2.0`, `vitest@5.0.3`, `@playwright/test@1.64.0`; `corepack enable` so pnpm 10.16.0 is used. Keep fonts, art, audio, overworld & battle helper modules. | `pnpm i && pnpm build` succeeds; `/` renders a placeholder page |
| **P0.4** | Secrets & config | ★ · 🔵 · 🔑 | `.env.example` (§4.5); `just init` writes `.env` with random `LABD_BRAIN_SECRET`/`LABD_PAIRING_SECRET` and prompts for keys; machine hygiene of §4.3.5 (ask the user before removing `NODE_TLS_REJECT_UNAUTHORIZED=0` from their shell profiles); `config/{lab,llm,roster,papers}.toml` with the defaults stated in §5.5.1, §6.5.2, §2.4, Part 8. | `just init` idempotent; `git status` shows no secrets |
| **P0.5** | Fetch everything (offline-first) | ★★ · 🔵 · 🌐 | `scripts/fetch_assets.sh` (PMD walkers for the roster species from `raw.githubusercontent.com/PMDCollab/SpriteCollab/master/sprite/<dex4>/…` + `credits.txt`; FireRed overworld humans from `pret/pokefirered/graphics/object_events/pics/people/`; cries from `PokeAPI/cries`; Showdown is already mirrored), `scripts/fetch_datasets.sh` (move the MNIST/tiny-NeRF/matbench files already in `data/raw/` — record sha256 — plus anything Part 8 adds), `scripts/fetch_papers.sh` (arXiv PDFs of the demo papers into `data/papers/`), fastembed model into `var/models/fastembed`. All write `data/SHA256SUMS`. | `just doctor` (stub) reports every file present with matching hashes |
| **P0.6** | Contracts skeleton | ★★ · 🔵 | `contracts/pokelab_contracts/` with `Envelope`, `JobSpec`, worker line models, `Command`, the event payload models of §10.2 (start with the ~20 used by P1–P4); `export.py` → `schemas/`; TS generation via `json-schema-to-typescript`; fixtures for each; validation tests in Python (pydantic), TS (ajv via vitest), Rust (serde round-trip). | `just contracts` regenerates and all three fixture suites pass |

**Exit:** skeleton builds in all three languages; all offline assets/datasets/papers present; contracts compile.

---

## P1 — `labd`, the Rust core ★★★★☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P1.1** | Store + writer thread | ★★★ · 🔵 | `lab-store`: open/migrate (DDL §10.4), WAL + pragmas; writer thread fed by `crossbeam`/`std::mpsc` with `(NewEvent, oneshot::Sender<i64>)`; group commit (≤ 512 ops or 10 ms); read-only connection pool for queries; `events_since`, `snapshot_put/get`; metrics batch insert; online backup. | tests `store_roundtrip`, `writer_crash_safety` (§5.11) green; 20 k events/s on a micro-bench |
| **P1.2** | Hub & WebSocket gateway | ★★★ · 🔵 | `lab-gateway`: axum router of §5.4.1 (health, bootstrap, events, jobs, metrics, artifacts, files, pair, telemetry, static); `/ws` protocol of §5.4.2 with the subscribe-then-replay fan-out order, per-subscriber bounded queues, metric coalescing, `resync` on `Lagged`, `Origin` check, ping/pong; `/internal/brain` socket of §5.4.3; command intake with schema validation + roles (§5.4.4). | `ws_resync` test; `websocat` session shows hello→welcome→events; a fake brain can publish and receive |
| **P1.3** | Metrics pipeline | ★★★ · 🔵 | `lab-metrics`: ring buffers, LTTB (+ Python reference test vector), 100 ms client frames (≤ 50 pts), full-rate brain feed (250 ms batches), 1 Hz `job.progress` rollups, `/api/jobs/:id/metrics?max_points`. | `lttb_reference` green; 10 k points/s fake stream → clients get ≤ 10 Hz frames, DB has all points |
| **P1.4** | Job engine & warm pool | ★★★★ · 🟣 | `lab-jobs`: resources & priority queues (§5.5.1); dedup by config hash (§5.5.2); warm pool spawn/prewarm/ready/assign/recycle/respawn (§5.5.3) with scrubbed env; JSON-lines parser (`LinesCodec`, 256 KB max) with concurrent stdout/stderr draining (§5.5.5); stderr ring; stop → SIGTERM(pgid) → SIGKILL via `process-wrap` (§5.5.4); pgid registry + orphan cleanup at startup; wall-clock timeouts; script jobs; background preemption. Test helper `tests/fake_worker.py` (emits metrics, honours stop, can crash, can spawn a grandchild). | `job_kill_tree`, `jsonl_parser_fuzz`, `fake_worker_e2e` green; no orphan PIDs after 100 random kill/crash cycles |
| **P1.5** | Telemetry & power guard | ★★ · 🔵 | `lab-telemetry`: NVML (fallback nvidia-smi CSV), sysinfo, AC + `powerprofilesctl get` (fallback EPP sysfs) (§5.7); `lab.warning{power}` logic; `/api/telemetry`. | HUD-ready JSON at 1 Hz; unplugging the charger produces the warning within 2 s |
| **P1.6** | Auth & pairing | ★★ · 🔵 | Roles (desk/phone/view/brain), pairing codes + QR SVG, HMAC tokens in HttpOnly cookies, path-traversal guards (§5.8, §11.4). | Phone (or `curl` with cookie) can claim a code once; second claim fails; `view` cannot POST commands |
| **P1.7** | Supervisor, CLI, replay, doctor | ★★★ · 🔵 | `labd up` startup sequence (§5.2) incl. brain child with restart/backoff; `labd replay <db> --speed`; `labd export`; `labd doctor` (§5.10 checks; stubs for parts not built yet clearly marked); ASCII QR + URL on start; structured logs. | `just up` starts labd + a dummy brain (`python -c` loop) that is restarted after `kill -9`; `labd replay` streams a fixture DB to a browser tab |

**Exit:** a fake worker's metrics stream through labd to a WebSocket client and the DB; kill semantics proven; replay works.

---

## P2 — Workers & the grokking kit ★★★☆☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P2.1** | Worker runtime | ★★ · 🔵 | `workers/pokelab_workers/{pool_main,protocol,emit,stop}.py`: stdin reader thread → job queue; `StopToken`; `Emitter` (line-buffered JSON, finite-check, rate limit per `emit` spec); prewarm dummy step; `ready` line; per-job run dir; exceptions → `error` line, worker survives. | worker passes the Rust `fake_worker` contract tests when swapped in |
| **P2.2** | Kit interface + `smoke` kit | ★★ · 🔵 | `kits/base.py`: `KitSpec` (name, version, `Config` pydantic model, target metric keys + direction, default budget, claim mapping), `run(cfg, emit, stop, run_dir)`, `analyze(run_dir)`. `smoke` kit: 2-layer MLP on random data (CPU/GPU) for tests. | `pytest workers/tests/test_kit_contract.py` green for `smoke` |
| **P2.3** | Grokking kit — models & data | ★★★ · 🔵 · 🔥 | Port `scripts/reference/grokbench/grok.py` into `kits/grokking/`: modular arithmetic datasets (add/sub/div/… mod p, Power's ops list in §8.2), **Nanda transformer** (1-layer, d=128, 4 heads, d_mlp=512, no LayerNorm, untied, learned pos-emb) and **Power transformer** (2-layer, causal, width 128, 4 heads) and the fast **MLP**; full-batch or minibatch; AdamW / Adam+L2 / Adam(wd=0) options (the regime differences matter for the comparator); Grokfast-EMA flag; init-scale α; float32/float64 softmax option; deterministic seeds; `stop_at` threshold. | CPU tiny config emits valid lines; GPU Nanda config reaches test acc ≥ 0.95 (record steps & seconds, `[MEASURED]` reference: 19.8 k steps / 62 s) |
| **P2.4** | Grokking telemetry hooks | ★★★ · 🔵 · 🔥 🧠 | Every `telemetry_every_steps`: total weight norm, W_E Fourier key-frequency power & Gini, restricted loss & excluded loss (Nanda; DFT over the full p×p logit table — only for the 1-layer model, ≤ 0.2 s per checkpoint), test-loss low-frequency oscillation power over a sliding window. Checkpoints at log-spaced steps for the analyst. | Telemetry curves show restricted loss falling **before** test loss on the reference run (plot saved to `var/reports/figures/grok_precursors.png`) |
| **P2.5** | Kit benchmark & pool sizing | ★★ · 🔵 · 🔥 | `scripts/bench.sh`: cold vs warm, 1×/2× concurrency for MLP and transformer, write `var/reports/bench.json`; confirm `pool.gpu_workers = 2` (`[MEASURED]` 3× is slower than 1× total throughput on AC). | `bench.json` written; numbers within 20 % of §11.1 |
| **P2.6** | W&B offline logging | ★ · 🔵 · 🔑 | `emit.py` optional W&B mirror (`WANDB_MODE=offline`, project `pokelab`, group/job_type/tags per §11.6); labd background `wandb sync` task (only when online). | A run appears in W&B after sync; with the network off the run is unaffected |

**Exit:** labd runs real grokking jobs on warm GPU workers with live metrics, telemetry, stop/kill and dedup.

---

## P3 — Brain foundation & the LLM router ★★★★☆

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P3.1** | Measure the gateway | ★ · 🔵 · 🔑 | `scripts/probe_llm.py`: per Elevate model, sequential calls at 1/2/4 req per 10 s until 429 → record ceiling, Retry-After behaviour, latency vs prompt size (0.5/2/6 k tokens), reasoning-token usage; Groq header limits. Run on a good network. | `var/reports/llm_probe.json`; `config/llm.toml` bucket defaults updated from it |
| **P3.2** | Bus client & state projection | ★★★ · 🔵 | `bus.py` (internal socket, publish batching, since-seq resume, request/response correlation for job submits); `state.py` projection (projects, plans, agents, tasks, jobs, approvals) with pure apply functions; `snapshot.py` (§6.12). | Replaying a recorded event stream twice yields identical state (hash) |
| **P3.3** | LLM router | ★★★★ · 🟣 · 🔑 | `llm/{providers,router,ratelimit,cache,budget}.py` per §6.5.3: provider adapters on the `openai` 3.28 SDK with `max_retries=0` (Elevate: `max_completion_tokens` vs `max_tokens` per model; Groq: custom User-Agent, per-organisation limits, compact-prompt variant ≤ 5 k tokens), token buckets with adaptive rates, circuit breakers, priority queue, request-size guard (46 KB), cache (live/llm-replay/record modes), budget ledger + `llm.call` events. Mock-provider test suite: 429 storms, 403 quota, timeouts, malformed bodies, UA rejection. | All router tests green; a 50-call soak against the real gateway produces zero unhandled errors and ≤ 1 visible 429 retry wait |
| **P3.4** | JSON I/O & repair | ★★ · 🔵 | `llm/jsonio.py`: tag extraction, fence stripping, `json_repair`, Pydantic validation with error messages suitable for a repair turn; 40 recorded real replies as fixtures (collect from P3.1/P3.3). | Fixture suite + Hypothesis fuzz green |
| **P3.5** | Brain main & supervision | ★★ · 🔵 | `main.py`: config, connect, rebuild state, start loops (§6.1), graceful shutdown; labd starts it for real (replace the dummy). Crash-recovery test: kill -9 during a fake project → resumes. | brain restarts in < 10 s with identical state hash |

**Exit:** the brain can talk to labd and to every LLM provider robustly, survive crashes, and spend tokens accountably.

---

## P4 — Agents & Professor Oak: the vertical slice ★★★★★

> Goal: *"Reproduce the grokking result of Nanda et al. / Power et al. and test weight decay = 0"* typed into a minimal console → the lab does it autonomously → report with verdict. No game yet.

| | Sub-phase | ★ · Model · Flags | Detail | Done when |
|---|---|---|---|---|
| **P4.1** | Paper ingestion | ★★★ · 🔵 | `papers/ingest.py` (PyMuPDF4LLM → sections → chunks → fastembed → `brain.db`), cached by sha256; `paper.read_section/search` tools. | Both grokking papers ingested in < 15 s each; section list sensible |
| **P4.2** | PaperPack extraction | ★★★★ · 🔵 · 🔑 | `papers/claims.py` + `packs.py` (§6.6.2): per-section-group `extract` calls, merge, validate, cite chunk ids; human review screen = `var/papers/<id>/pack.json` + diff tool (`just pack-review <id>`) → `paper.pack_corrected` events. Compare against the ground truth in §8.2. | Pack for Power et al. contains p=97, 2-layer, AdamW lr 1e-3, wd 1, β2 0.98, warm-up 10, batch min(512, N/2), budget 1e5 + the wd=0 Fig. 1 regime; Nanda pack contains p=113, 1-layer, d=128, frac 0.3, full batch, 40 k epochs — ≥ 90 % fields right before review |
| **P4.3** | Specs, roster & tools | ★★★ · 🔵 | `agents/spec.py` (AgentSpec §6.4.2), `config/roster.toml` (§2.4 base roster with role prompts in `agents/prompts/*.md`), tools of §6.4.3 needed for the slice (paper.*, memory.search (stub), code.read/write/edit, job.submit/status/metrics/stop, analysis.run, notes.write, human.ask, finish), each with Pydantic args and permission lists. | Tool unit tests green; roster loads 9 base agents |
| **P4.4** | Agent runtime + action protocol | ★★★★★ · 🟣 · 🔑 | `agents/{runtime,protocol,context}.py` exactly per §6.3: loop, `<thought>/<action>/<final>`, parse+repair+validation, observation truncation, context packs with budgets, per-task budgets, events (`agent.thought/action/action_result/task_*`). Prompt tail `_protocol.md` with 2 worked examples. | 20 scripted mini-tasks (read a section, edit a file, submit a smoke job, finish) succeed ≥ 18/20 on the real gateway; format-error rate < 10 % |
| **P4.5** | Capability analysis | ★★★ · 🔵 · 🔑 | `oak/capabilities.py` (§6.2.2) — LLM proposal constrained to the taxonomy + coverage from a stub Scout (cosine of role/capability embeddings; real Scout in P5.6). | Event emitted with reasons for 5 test requests; sensible gaps for a materials request |
| **P4.6** | Planner + templates | ★★★★ · 🔵 · 🔑 | `oak/planner.py` + `templates/{reproduce,whatif,compare,explore,discover}.yaml` (§6.2.3); LLM adaptation; DAG validation; plan events; redirect revision function (§6.2.8). | Valid plans for 5 test requests; invalid LLM plans are rejected and repaired once |
| **P4.7** | Scheduler + verifiers | ★★★★ · 🟣 | `oak/scheduler.py` (§6.2.4) with concurrency limits, retries with re-selection, escalation; `agents/verifiers.py` (§6.3.5); interim Selector = Thompson with Beta(2,2) (full Selector in P5.5). | Fake-LLM end-to-end test runs a 7-step plan to completion deterministically |
| **P4.8** | Reward v1 | ★★ · 🔵 | `reward.py` exactly §6.9 (without project credit); `agent.rewarded` events. | Unit tests on the formula incl. "fast failure ≤ 0.2" |
| **P4.9** | Comparator v1 | ★★★ · 🔵 · 🔑 | `science/comparator.py` §6.10.1–6.10.2 + 6.10.4 (no diagnostics yet); grokking checklist YAML (17 items, §8.2); claim guard; `comparison.md`. | Report for the reference run lists ≥ 3 sourced hypotheses and passes the claim guard |
| **P4.10** | **Vertical slice** | ★★★★ · 🔵 · 🔥 🔑 | Minimal console page (`web/app/slice/page.tsx` or a Python TUI): request box, event feed, run curve, report. Run the slice: reproduce → wd=0 what-if → report. Record the session (`labd export var/sessions/slice_v1.db`) — the first REPLAY fixture and the frontend's development fixture. | AC-1 and AC-2 (without Oracle kills) pass; AC-3 partially (no diagnostics); session recorded |

**Exit — the backend is demo-able on its own.**
