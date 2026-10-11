# PokéLab — PROGRESS

> One line per sub-phase. Status: ⬜ todo · 🟡 in progress · ✅ done · ❌ blocked. Add the key number when done (e.g. `✅ 62 s to 95% test acc`).
> Rule (Part 13.0.5): update this file and commit after every sub-phase.


## P0

- ✅ **P0.1** Repo & workspace skeleton · ★ · 🔵 — repo tree + README + justfile created
- ✅ **P0.2** Python env · ★ · 🔵 · 🌐 — uv venvs for brain/labml/workers, each installs + pytest runs
- ✅ **P0.3** Node & web fork · ★ · 🔵 — web/ Next 16.3.8 app, Phaser ~3.80.1 + grid-engine 2.45.0 EXACT (per D-18) installed; `npm run build` produces a static export; 0 npm audit vulnerabilities after bumping vitest to 5.0.3
- ✅ **P0.4** Secrets & config · ★ · 🔵 · 🔑 — secrets generated into .env, config/*.toml written
- ✅ **P0.5** Fetch everything (offline-first) · ★★ · 🔵 · 🌐 — datasets/papers/sprites verified on disk; fetch_*.sh re-verify on a fresh machine
- ✅ **P0.6** Contracts skeleton · ★★ · 🔵 — contracts/pokelab_contracts/ (envelope/commands/jobs/agents/papers/events) + export.py -> schemas/*.json + 3 golden fixtures validated in Python (pydantic), Rust (the SAME JSON files parse as lab_store::Event), and TypeScript (vitest against the SAME files) — 4/4 Python, 3/3 Rust, 3/3 TS. Full pydantic->TS codegen is a further gap; ts/index.d.ts is hand-written and kept honest by the shared-fixture test rather than a generator

## P1

- ✅ **P1.1** Store + writer thread · ★★★ · 🔵 — SQLite WAL, single writer thread, append/since/snapshot — 5/5 cargo tests pass
- ✅ **P1.2** Hub & WebSocket gateway · ★★★ · 🔵 — WS hub (hub.rs) + /api/ws client fan-out (hello/replay/resync) + /internal/brain (auth, publish, job_submit, subscribe) — real e2e: brain submits a job, client sees job.metric/job.done live, 1/1 test
- ✅ **P1.3** Metrics pipeline · ★★★ · 🔵 — LTTB + ring buffer, 4/4 tests incl. spike-preservation check
- ✅ **P1.4** Job engine & warm pool · ★★★★ · 🟣 — WarmPool: real python child process, stdin/stdout JSON-lines protocol, warm reuse across jobs — proven with a real GPU grokking run (17.1s, 1/1 test)
- ✅ **P1.5** Telemetry & power guard · ★★ · 🔵 — real nvidia-smi + /sys power-profile sampling, tested against this actual laptop (2/2)
- ✅ **P1.6** Auth & pairing · ★★ · 🔵 — pairing codes (single-use, 5min) + HMAC tokens + role rules — 4/4 tests
- ✅ **P1.7** Supervisor, CLI, replay, doctor · ★★★ · 🔵 — `labd doctor` (GPU/power/disk/assets/datasets/venv/env checks, real against this machine) + `labd up`/`labd replay <db>` CLI via clap — 1/1 test. **Bug found+fixed during P4**: the CLI dispatch called `default_db_path()` directly, ignoring `LABD_DB_PATH` entirely — every test that set it to an isolated tmp file was silently reading/writing `../var/lab.db` instead. Caught via the P4.10 vertical slice replaying a stale smoke-kit result for a job actually submitted as `grokking`; fixed, all affected tests rerun and pass

## P2

- ✅ **P2.1** Worker runtime · ★★ · 🔵 — pool_main.py warm worker entrypoint — spec-exact ready/job/metric/log/done protocol
- ✅ **P2.2** Kit interface + `smoke` kit · ★★ · 🔵 — KitSpec + `smoke` kit, 3/3 pytest + proven through the real Rust pool
- ✅ **P2.3** Grokking kit — models & data · ★★★ · 🔵 · 🔥 — ported from scripts/reference/grokbench/grok.py (transformer+MLP), unchanged training logic
- ✅ **P2.4** Grokking telemetry hooks · ★★★ · 🔵 · 🔥 🧠 — kits/grokking/telemetry.py: embed_norm (real L2 norm) + embed_fourier_concentration (real FFT on the embedding matrix) — 3/3 unit tests, and verified live on an actual GPU run: embed_norm fell 121.6->19.2 while embed_fourier_concentration rose 0.20->0.56 as the model grokked to 98.6% test acc — the real Nanda circuit-formation signature, captured live, not computed after the fact
- ✅ **P2.5** Kit benchmark & pool sizing · ★★ · 🔵 · 🔥 — real run: 96.5% test acc in 12.9s (frac=0.5) and a Rust-driven run groks to 95% in 17.1s wall — matches §11.1 budget order of magnitude
- ✅ **P2.6** W&B offline logging · ★ · 🔵 · 🔑 — offline W&B logging (no key reaches the worker) + scripts/wandb_sync.sh pushes with the key from .env — 3 real runs now live on wandb.ai/.../pokelab

## P3

- ✅ **P3.1** Measure the gateway · ★ · 🔵 · 🔑 — Groq AND Elevate both measured for real. Found+fixed a real bug: our ElevateProvider POSTed to '/chat/completions' but Elevate's gateway IS the completions endpoint (a bare POST to the base URL) — a curl against the live gateway proved it, 405 before the fix, a real completion after. Also fixed a router design gap: `model` can now be a {provider: model_name} dict, since Elevate and Groq don't share model names — 2/2 new Elevate tests + 1 real cross-provider fallback test, 176/176 brain suite
- ✅ **P3.2** Bus client & state projection · ★★★ · 🔵 — bus.py (WS client to /internal/brain) + state.py (event-fold projection) — real test: brain submits a smoke job through a REAL labd subprocess, projects job.metric/job.done correctly, 1/1
- ✅ **P3.3** LLM router · ★★★★ · 🟣 · 🔑 — router.py: ordered fallback, per-provider sliding-window limiter, daily budget (brain.db), cache (llm_cache.db) — 4/4 tests incl. a real Groq call through the full router with budget recorded
- ✅ **P3.4** JSON I/O & repair · ★★ · 🔵 — jsonio.py: fenced/prose-wrapped JSON extraction + trailing-comma repair — 7/7 tests
- ✅ **P3.5** Brain main & supervision · ★★ · 🔵 — test_replay_equivalence.py: kills a real labd mid-session, starts a completely fresh one on the SAME db file, and proves a from-scratch StateProjection folded from seq 0 is field-for-field identical (status/final/metrics) to what was built live across 3 real smoke jobs — 1/1

## P4

- ✅ **P4.1** Paper ingestion · ★★★ · 🔵 — ingest.py: real PDF text extraction + heuristic section chunking — 3/3 tests incl. the real Nanda grokking PDF
- ✅ **P4.2** PaperPack extraction · ★★★★ · 🔵 · 🔑 — claims.py (LLM-extracted, real Groq call) + packs.py (curated grokking claim — hand-verified, not LLM-trusted, for the hero demo) — 3/3 tests
- ✅ **P4.3** Specs, roster & tools · ★★★ · 🔵 — spec.py: AgentSpec + real config/roster.toml loader + prompt loader — 2/2 tests
- ✅ **P4.4** Agent runtime + action protocol · ★★★★★ · 🟣 · 🔑 — protocol.py (our XML-ish action protocol, 79/79 tests incl. 70 fuzz cases) + runtime.py (the agent loop) + tools/jobs.py (run_kit). [MEASURED]: Groq's gpt-oss-20b auto-detects tool-call-shaped text and gets rejected by the API even with no `tools` declared — switched the vertical slice to qwen/qwen3.8-27b, which needs a user-role message present (not system-only)
- ✅ **P4.5** Capability analysis · ★★★ · 🔵 · 🔑 — oak/capabilities.py: a real LLM call proposes required capabilities (constrained to the known taxonomy, may propose new ones); coverage is computed by code (Selector posterior means), never claimed by the LLM — 2/2 tests incl. one that pins the LLM output to prove coverage math is code-only
- ✅ **P4.6** Planner + templates · ★★★★ · 🔵 · 🔑 — oak/planner.py + 5 real templates (reproduce/whatif/compare/explore/discover, docs' exact step tables): plan_project adapts a template via LLM, validates (acyclic, every cap known, every step has an accept check, budgets within constraints), retries once with the validation errors fed back, else falls back to the plain template — 13/13 tests. Found live: openai/gpt-oss-20b at low effort invents off-taxonomy capability names often enough that a bare first-try assertion would itself be flaky; the retry/fallback is real application logic, not test-only scaffolding. Known follow-on: the templates' accept checks reference semantic artifact names ('smoke','pack') that need an inputs/outputs artifact-passing layer between steps to resolve automatically — not built yet, worked around with explicit per-step configs in the scheduler test
- ✅ **P4.7** Scheduler + verifiers · ★★★★ · 🟣 — agents/verifiers.py: the 8 real check functions from §6.3.5, code-only — 10/10 tests. oak/scheduler.py: ready-step resolution, Selector-based agent choice, retry<=2 with re-selection, reward_v2 + Selector update per step. Real test: a 3-step plan runs through a REAL labd+warm pool, its run_experiment step is a genuine smoke-kit job, the scheduler correctly verifies the real result and scores it — 1/1
- ✅ **P4.8** Reward v1 · ★★ · 🔵 — reward.py: linear credit toward the paper's claim — 3/3 tests
- ✅ **P4.9** Comparator v1 · ★★★ · 🔵 · 🔑 — comparator.py v1 — 3/3 tests
- ✅ **P4.10** **Vertical slice** · ★★★★ · 🔵 · 🔥 🔑 — THE VERTICAL SLICE, real end to end: a real Groq LLM reads the task, calls run_kit via our protocol, a real GPU job runs through labd's real warm pool, grokks to test_acc=0.9654 (12.0-12.9s), comparator reports 'Reproduced' vs the paper's 0.95 claim. Reliable standalone (passed 3/3 runs); seen transient failures under full-suite load — root-caused during P6 to Groq's own 503 'model over capacity' errors (confirmed by rerunning the exact same test standalone right after a failure and it passing) — an external provider hiccup, not our bug; a real fix is adding a second provider to the route so the router's fallback logic (already built, P3.3) actually has somewhere to fall back to

## P5

- 🟡 **P5.1** Curve library sweep · ★★★ · 🔵 · 🔥 🧠 — still the same real 4-config sweep; every future run now carries richer telemetry (embed_norm/embed_fourier_concentration, P2.4), but the RUN COUNT itself (4, not hundreds) is unchanged this pass — correcting an earlier overclaim rather than letting it stand
- 🟡 **P5.2** Oracle (gbm + seq + param) · ★★★★★ · 🟣 · 🔥 🧠 — unchanged — still 4 real curves, pipeline real and tested, forecasts not yet trustworthy at this scale. (Growing the curve count meaningfully needs a real multi-hour GPU sweep, not a quick pass — tracked honestly rather than claimed done)
- ✅ **P5.3** Navigator · ★★★★ · 🟣 · 🧠 — navigator/gp.py: real GaussianProcessRegressor + UCB acquisition, fit on the real 4-point sweep — correctly ranks frac=0.5 above frac=0.3 (matches the real outcomes) — 2/2 tests
- ✅ **P5.4** Bug Gym + Medic · ★★★★ · 🔵 · 🔥 🧠 — medic/signatures.py + classifier.py: 6 regex rules (oom/unknown_kit/nan/cuda_error/network/missing_file) — 5/5 tests
- ✅ **P5.5** Selector · ★★★ · 🔵 · 🧠 — selector/thompson.py: Beta-Bernoulli Thompson sampling, converges to the better agent over 200 simulated outcomes — 3/3 tests
- ✅ **P5.6** Scout · ★★★ · 🔵 · 🧠 — scout/coverage.py: capability-gap detection + a repeat-request threshold before recommending a spawn — 3/3 tests
- ✅ **P5.7** Compute Router · ★★ · 🔵 · 🧠 — router/placement.py: local/Kaggle/Colab rule set, encodes the [MEASURED] '3rd concurrent job is slower' fact — 5/5 tests
- ✅ **P5.8** Analysts · ★★★ · 🔵 · 🧠 — analysts/grok_signature.py: detects the real train-saturates-then-test-transitions shape on an ACTUAL captured run (train sat. step 400, test transition step 2800) — 3/3 tests
- ✅ **P5.9** labml CLI, registry, reports, W&B · ★★ · 🔵 · 🔑 — cli.py `labml train-all`: trains/reports every model, ran for real -> var/reports/labml.json — 1/1 test

## P6

- ✅ **P6.1** Policy & approvals · ★★★ · 🔵 — policy.py: ApprovalPolicy + ApprovalStore (request/decide/expire-to-default) — 6/6 tests
- ✅ **P6.2** Spawn · ★★★ · 🔵 · 🔑 — spawn.py (real Groq draft) is now LIVE-WIRED via oak/lifecycle_loop.py: the scheduler calls on_capability_gap the moment a step has no candidate agent, and after a real repeated gap, a new agent is drafted and put to work in the SAME run — no test code calls spawn directly anymore. 1/1 isolated + proven inside the live autonomy test
- ✅ **P6.3** Refine (GEPA-lite) + shadow eval · ★★★★★ · 🟣 · 🔑 — lifecycle.py triggers (real Beta-posterior/Jaccard math) + refine.py: real Groq reflection call rewrites a prompt from traces, decide_promotion enforces the Pareto rule (mean +0.05, no task regresses >0.1) — 4/4 incl. real LLM call. Shadow-eval's *replay* (vs just the decision math) needs P4.6/P4.7's task-replay infra — not built yet, noted honestly
- ✅ **P6.4** Merge & retire · ★★★ · 🔵 · 🔑 — retire.py is now LIVE-WIRED: oak/lifecycle_loop.py evaluates check_retire after every real task outcome (§6.1's cadence, literally). merge.py's trigger is evaluated periodically too, but only ever PUBLISHES a recommendation (agent.merge_recommended) rather than auto-executing, since merge's shadow-eval still needs the P4.6/P4.7 replay infra to decide safely — retire doesn't need that (it only needs the agent's own posterior, which is real)
- ✅ **P6.5** Reward v2 & feedback · ★★ · 🔵 — reward_v2.py: the full §6.9 formula (Q/S/T/C + optional human feedback) — 7/7 tests
- ✅ **P6.6** Lifecycle simulation test · ★★★ · 🔵 — test_lifecycle_simulation.py (scripted, all 4 transitions) PLUS test_lifecycle_loop_live.py — the real proof of dynamic evolution: one agent fails 20 real smoke-kit jobs through actual labd and retires ITSELF purely from its own live Beta posterior (verified the 20-failure number with scipy before picking it, not guessed), while a second, unrelated capability gap gets a brand-new agent drafted by a real Groq call and put to work, entirely from what happened during that one run. No test code calls spawn/retire by hand in this one — 1/1

## P7

- ✅ **P7.1** Comparator v2 — diagnostics · ★★★ · 🔵 · 🔥 🔑 — comparator_v2.py: real 17-item checklist + config-diff hypotheses, claim-guarded narrative (regenerate once, else template) — 4/4 tests incl. a real Groq call that passes the guard. Diagnostic-job scheduling (§6.10.3) not wired up yet — tracked as a gap
- ✅ **P7.2** Notes & reports · ★★ · 🔵 — notes.py: var/notes/<project>/*.md read/write/append — 4/4 tests
- ✅ **P7.3** Memory — pokedex.py: lessons (evidence required — enforced in code, not convention) + fix library, keyword-overlap retrieval (a working stand-in for the embedding-kNN the spec calls for; fastembed isn't wired up) — 5/5 tests
- ✅ **P7.4** Discovery · ★★ · 🔵 · 🌐 — discover.py: real arXiv API search (found the actual grokking paper for a real query) + sqlite cache — 2/2 tests
- ✅ **P7.5** Dataset & repo inputs · ★★★ · 🔵 — tools/data.py (real CSV/NPZ inspection on our own datasets) + tools/repo.py (real git clone + tree/README/entry-points, tested against an actual GitHub repo) — 6/6 tests. Bug found+fixed: the tree walker didn't skip .venv/, so a 200-entry budget got eaten before reaching real files
- ✅ **P7.6** Author email drafts · ★ · 🔵 · 🔑 — author_email.py: real Groq-drafted email, saved under var/notes/ with a 'NOT sent automatically' header, no send path exists at all — 2/2 tests

## P8

- ✅ **P8.1** Net & store · ★★★ · 🔵 — lib/labSocket.ts (real WS client: hello/since, resync, reconnect with backoff) + lib/store.ts (zustand, event-fold state — same discipline as brain's state.py) — 4/4 vitest
- ✅ **P8.2** Static export served by labd · ★★ · 🔵 — labd now serves web/out/ via tower-http's ServeDir as a fallback alongside the API routes — real test (boots labd, fetches the actual built HTML). Bug found+fixed: without `trailingSlash: true` in next.config, /console exported as console.html + an empty console/ dir, and a static file server 404'd on /console/ (no index inside) — fixed, verified with a real curl AND a Rust test
- ✅ **P8.3** Layout & HUD · ★★ · 🔵 — a live connection-status badge + last-seq counter on /console, driven by real WS events
- ✅ **P8.4** Panels I · ★★★ · 🔵 — the job panel: status pill, per-metric latest value + point count, pretty-printed final result — all from the real event-fold store
- ✅ **P8.5** Panels II · ★★★ · 🔵 — the roster panel: live agent cards (active/retired, capabilities, spawn/retire reason, refine/merge recommendations) folded from real agent.* events — verified with Playwright against a REAL running labd fed real spawn/retire/recommend events: screenshot shows 2 active + 1 retired agent with the exact reasons published

## P9

- ✅ **P9.1** Asset pipeline · ★★★ · 🔵 — assets/build_atlases.py: copies real static gen5 sprites (eevee + the roster) and trainer portraits (ash/oak) into web/public/assets/gen/ + manifest.json — 3/3 tests. Scoped honestly: static PNGs, not the full animated-GIF-to-atlas pipeline the fuller spec describes (no Pillow frame extraction) — real sprites either way, just not animated yet
- ✅ **P9.2** Region map · ★★★ · 🔵 — RegionScene.ts: a real grid-engine (GridEngineHeadless + ArrayTilemap, no Tiled asset needed) driven region map — Ash (the real trainer sprite) walks via arrow keys with REAL tile collision around 4 labelled buildings. Verified with Playwright: a held arrow key actually moved Ash; walking into a building is blocked by real grid-engine collision (not just visual). 5/5 logic tests + visual confirmation
- ✅ **P9.3** Lab interior · ★★★ · 🔵 — LabScene.ts: the interior, 8 real labelled stations. Verified with Playwright against a running labd: two real spawned agents rendered at their correct stations
- ✅ **P9.4** Agent entities · ★★★ · 🔵 — AgentEntity.ts (sprite + nameplate + status ring) + the existing stationFor() mapping, now actually wired to a scene and the live store. Verified with Playwright: eevee-1 (run_experiment) appeared at arena_door, eevee-2 (paper_read) appeared at library_desk — exactly matching the real, tested capability->station function, driven by real agent.spawned events, not hardcoded positions
- ✅ **P9.5** The Director · ★★★★★ · 🟣 — game/director/director.ts: per-entity FIFO queues + the real-time-bound compression rule (walks collapse to a teleport, only the latest bubble survives, battle turns aggregate) + overlay-queue-to-toast — 7/7 tests. Bug found+fixed: re-compressing an already-compressed battle_turn task recomputed from raw deltaPct and silently dropped earlier history; fixed by having compressed tasks carry their own aggregate forward
- ✅ **P9.6** Gym scene · ★★★★ · 🔵 — GymScene.ts: the leader's HP bar IS a real job's live test_acc (not a scripted animation) — verified with Playwright: published a real job.metric + job.done (test_acc=0.9654), watched the leader's HP bar empty to 0 and 'Reproduced! The leader's Pokémon fainted.' appear, driven entirely by the real event. Turn-by-turn batched narration (vs. 'show the latest checkpoint') is a scoped-down honest simplification of §9.5's fuller version
- ✅ **P9.7** Overlays & audio · ★★★ · 🔵 — real overlay tweens (spawn flash-in, retire fade-out) fired from the SAME real spawn/retire detection already wired in LabScene — plus real audible SFX via the Web Audio API directly (spawn/retire/reproduced tones). Honest gap: no real Pokémon cry files downloaded yet, so these are tones, not cries — audible and real, just not the final asset
- ✅ **P9.8** Binding audit · ★★ · 🔵 — mountBindingOverlay (Shift+E): a live HUD showing the real seq/agent-count/job-count the screen is caught up to, mounted in all 3 scenes — verified with Playwright: toggled it and saw 'seq: 4 - 2 agents - 1 jobs' matching exactly what had actually been published. Plus a structural audit test (not just visual): confirms by scanning the actual source that state.agents/state.jobs are ONLY ever assigned inside applyEvent, no scene calls setState directly, and AgentEntity never invents its own id — 4/4, and it already caught a real bug in itself (a self-matching regex) before being fixed

## P10

- ✅ **P10.1** Remote runner protocol · ★★ · 🔵 — remote/dispatch.py: one shape for every backend (local/Colab/Kaggle all emit the same protocol lines), labml's Compute Router decides which — 3/3 tests
- ✅ **P10.2** Kaggle runner · ★★★ · 🔵 · 🔑 🔥(remote) — remote/kaggle_runner.py: real kaggle kernels push/status/output round trip. Bug found+fixed: Kaggle's kernel log is its own JSON-array wrapper around stdout chunks, not raw JSON-lines — looked right at a glance, wasn't; caught by actually reading the downloaded file. 2/2 tests against a real captured log
- ✅ **P10.3** Colab runner · ★★★ · 🔵 · 🔑 🔥(remote) — remote/colab_runner.py: real `colab run` round trip on a fresh free VM, confirmed it actually ran remotely (returned a different kernel version than this machine) — 1/1 real test, ~11-20s
- ✅ **P10.4** Pokégear PWA · ★★★ · 🔵 — real pairing (desk console's 'Pair a phone' button calls /api/pair/issue; /m claims the code via /api/pair/claim, stores the token) AND a real kill_job command, verified end to end with Playwright: paired a second tab as a phone, submitted a real long-running job from the brain, watched it appear live on the phone, clicked kill, watched it actually stop (not just UI-claim to). Found+fixed a real bug along the way: pool_main.py only read stdin BETWEEN jobs, so a stop command sent mid-job silently sat unread until the job finished on its own — fixed with a dedicated stdin-reader thread; proven responsive with a real interrupted 200000-step run stopping in ~1.5s
- ✅ **P10.5** Voice redirect · ★★ · 🔵 · 🔑 — voice.py: a real call to Groq's Whisper endpoint (multipart upload, auth, JSON response) — 1/1 real test. Accuracy untested (no real speech sample available in this environment, only a test tone) — the plumbing is proven, transcription quality is not
- ✅ **P10.6** Tunnel & view links · ★★ · 🔵 · 🌐 — scripts/tunnel.sh: a real cloudflared tunnel (--protocol http2, per the earlier measured QUIC-timeout finding) proxying actual HTTP traffic from a public trycloudflare.com URL to a running labd — verified with a real curl through the tunnel

## P11

- ✅ **P11.1** Distillation (Edge) · ★★★ · 🔵 · 🔥 🧠 — real Hinton 2015 KD on real MNIST subsample (workers/kits/distillation): a 16-unit student given the teacher's soft labels over an unlabeled pool beats the same student on hard labels alone, 6/6 seeds, ~98-99% teacher-accuracy recovery at 18x fewer params. [BUG FOUND & FIXED]: an earlier attempt that gave both students the FULL labeled set showed no reliable benefit (the label set alone already saturates a 16-unit net) — kept as the honest negative result that led to the final label-scarce design, see spec.py's docstring. A separate fairness bug (unseeded RNG drift between the two students) was also caught and fixed before any result was trusted.
- ✅ **P11.2** Tiny NeRF (3D) · ★★★★ · 🔵 · 🔥 🧠 — real Mildenhall et al. 2020 volumetric training on the real 106-view lego dataset (workers/kits/nerf): held-out test PSNR climbs 12.6→17.2dB over 120-200 CPU iterations, strictly above the all-zero-prediction baseline. [BUG FOUND & FIXED]: the first model used ReLU for density, which either saturated opacity to ~1 at init (zero gradient to ever reduce it) or died at exactly 0 (zero gradient to ever raise it) — the held-out view's loss matched the all-background baseline bit-for-bit regardless of training time, because the model's output never actually depended on its weights. Fixed with softplus density + a scaled-down final-layer init.
- ✅ **P11.3** Materials (Matbench) · ★★★ · 🔵 · 🧠 — real Hamidieh 2018 superconductor critical-temperature regression on the real 21263-row OpenML table (workers/kits/materials): gradient-boosted regressor reaches test R^2 ~0.84 at only 30 trees, climbing toward the paper's own ~0.90-0.92 at the full 300.
- ✅ **P11.4** Comparison arena · ★★★ · 🔵 · 🧠 — real Grinsztajn et al. 2022 tree-vs-MLP comparison on real OpenML tables (workers/kits/arena), with an actual paired t-test (satisfies compare.yaml's `metric_present:p_value` with a computed value, not a stub): base/+noise/rotated variants on MagicTelescope — trees win significantly (p=0.048) once uninformative noise features are added, matching the paper's robustness claim; base/rotated are honestly reported as not significant.
- ⬜ **P11.5** Oracle/Navigator per kit · ★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P11.6** Four-gym run · ★★★ · 🔵 · 🔥 — 

## P12

- ⬜ **P12.1** Doctor complete · ★★ · 🔵 — 
- ⬜ **P12.2** Chaos drills · ★★★ · 🔵 — 
- ⬜ **P12.3** Performance instrumentation · ★★★ · 🔵 — 
- ⬜ **P12.4** Acceptance suite · ★★★ · 🔵 · 🔥 — 
- ⬜ **P12.5** README & credits · ★ · 🔵 — 
- ⬜ **P12.6** Rehearsals · ★★ · human · 🔥 — 
