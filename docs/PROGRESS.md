# PokéLab — PROGRESS

> One line per sub-phase. Status: ⬜ todo · 🟡 in progress · ✅ done · ❌ blocked. Add the key number when done (e.g. `✅ 62 s to 95% test acc`).
> Rule (Part 13.0.5): update this file and commit after every sub-phase.


## P0

- ✅ **P0.1** Repo & workspace skeleton · ★ · 🔵 — repo tree + README + justfile created
- ✅ **P0.2** Python env · ★ · 🔵 · 🌐 — uv venvs for brain/labml/workers, each installs + pytest runs
- ✅ **P0.3** Node & web fork · ★ · 🔵 — web/ Next 16.3.8 app, Phaser ~3.80.1 + grid-engine 2.45.0 EXACT (per D-18) installed; `npm run build` produces a static export; 0 npm audit vulnerabilities after bumping vitest to 5.0.3
- ✅ **P0.4** Secrets & config · ★ · 🔵 · 🔑 — secrets generated into .env, config/*.toml written
- ✅ **P0.5** Fetch everything (offline-first) · ★★ · 🔵 · 🌐 — datasets/papers/sprites verified on disk; fetch_*.sh re-verify on a fresh machine
- 🟡 **P0.6** Contracts skeleton · ★★ · 🔵 — no contracts/ package yet — events/commands only typed ad hoc in lab-store/lab-jobs so far

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
- 🟡 **P2.4** Grokking telemetry hooks · ★★★ · 🔵 · 🔥 🧠 — basic train/test acc+loss streamed live; weight-norm/Fourier analysis (the deeper telemetry) not ported yet
- ✅ **P2.5** Kit benchmark & pool sizing · ★★ · 🔵 · 🔥 — real run: 96.5% test acc in 12.9s (frac=0.5) and a Rust-driven run groks to 95% in 17.1s wall — matches §11.1 budget order of magnitude
- ✅ **P2.6** W&B offline logging · ★ · 🔵 · 🔑 — offline W&B logging (no key reaches the worker) + scripts/wandb_sync.sh pushes with the key from .env — 3 real runs now live on wandb.ai/.../pokelab

## P3

- ✅ **P3.1** Measure the gateway · ★ · 🔵 · 🔑 — Groq AND Elevate both measured for real. Found+fixed a real bug: our ElevateProvider POSTed to '/chat/completions' but Elevate's gateway IS the completions endpoint (a bare POST to the base URL) — a curl against the live gateway proved it, 405 before the fix, a real completion after. Also fixed a router design gap: `model` can now be a {provider: model_name} dict, since Elevate and Groq don't share model names — 2/2 new Elevate tests + 1 real cross-provider fallback test, 176/176 brain suite
- ✅ **P3.2** Bus client & state projection · ★★★ · 🔵 — bus.py (WS client to /internal/brain) + state.py (event-fold projection) — real test: brain submits a smoke job through a REAL labd subprocess, projects job.metric/job.done correctly, 1/1
- ✅ **P3.3** LLM router · ★★★★ · 🟣 · 🔑 — router.py: ordered fallback, per-provider sliding-window limiter, daily budget (brain.db), cache (llm_cache.db) — 4/4 tests incl. a real Groq call through the full router with budget recorded
- ✅ **P3.4** JSON I/O & repair · ★★ · 🔵 — jsonio.py: fenced/prose-wrapped JSON extraction + trailing-comma repair — 7/7 tests
- 🟡 **P3.5** Brain main & supervision · ★★ · 🔵 — main.py: reconnect-with-backoff loop against real labd, survives a labd restart without crashing (1/1) — full event-for-event replay-equivalence check deferred to P4 (needs real brain-side state to diff)

## P4

- ✅ **P4.1** Paper ingestion · ★★★ · 🔵 — ingest.py: real PDF text extraction + heuristic section chunking — 3/3 tests incl. the real Nanda grokking PDF
- ✅ **P4.2** PaperPack extraction · ★★★★ · 🔵 · 🔑 — claims.py (LLM-extracted, real Groq call) + packs.py (curated grokking claim — hand-verified, not LLM-trusted, for the hero demo) — 3/3 tests
- ✅ **P4.3** Specs, roster & tools · ★★★ · 🔵 — spec.py: AgentSpec + real config/roster.toml loader + prompt loader — 2/2 tests
- ✅ **P4.4** Agent runtime + action protocol · ★★★★★ · 🟣 · 🔑 — protocol.py (our XML-ish action protocol, 79/79 tests incl. 70 fuzz cases) + runtime.py (the agent loop) + tools/jobs.py (run_kit). [MEASURED]: Groq's gpt-oss-20b auto-detects tool-call-shaped text and gets rejected by the API even with no `tools` declared — switched the vertical slice to qwen/qwen3.8-27b, which needs a user-role message present (not system-only)
- ⬜ **P4.5** Capability analysis · ★★★ · 🔵 · 🔑 — capability analysis not built — the vertical slice skips straight to a hardcoded task, no gap detection yet
- ⬜ **P4.6** Planner + templates · ★★★★ · 🔵 · 🔑 — no planner/templates — the task given to the agent is hardcoded in the test, not decided by Oak
- ⬜ **P4.7** Scheduler + verifiers · ★★★★ · 🟣 — no multi-step scheduler/verifiers — the agent loop calls one tool directly, no plan-with-steps abstraction yet
- ✅ **P4.8** Reward v1 · ★★ · 🔵 — reward.py: linear credit toward the paper's claim — 3/3 tests
- ✅ **P4.9** Comparator v1 · ★★★ · 🔵 · 🔑 — comparator.py v1 — 3/3 tests
- ✅ **P4.10** **Vertical slice** · ★★★★ · 🔵 · 🔥 🔑 — THE VERTICAL SLICE, real end to end: a real Groq LLM reads the task, calls run_kit via our protocol, a real GPU job runs through labd's real warm pool, grokks to test_acc=0.9654 (12.0-12.9s), comparator reports 'Reproduced' vs the paper's 0.95 claim. Reliable standalone (passed 3/3 runs); seen transient failures under full-suite load — root-caused during P6 to Groq's own 503 'model over capacity' errors (confirmed by rerunning the exact same test standalone right after a failure and it passing) — an external provider hiccup, not our bug; a real fix is adding a second provider to the route so the router's fallback logic (already built, P3.3) actually has somewhere to fall back to

## P5

- 🟡 **P5.1** Curve library sweep · ★★★ · 🔵 · 🔥 🧠 — a real 4-config sweep (frac 0.3/0.4/0.5/0.6) ran on this GPU through the actual warm pool (one process, 4 jobs) — real curves captured to labml/tests/fixtures/grok_sweep.json; the full hundreds-of-runs sweep the spec calls for hasn't run
- 🟡 **P5.2** Oracle (gbm + seq + param) · ★★★★★ · 🟣 · 🔥 🧠 — features.py + gbm.py (GBM with a logistic-regression fallback below 50 samples) — pipeline works end to end, trained on the 4 real curves above (2/2 tests); NOT validated at the scale needed to trust its forecasts
- ✅ **P5.3** Navigator · ★★★★ · 🟣 · 🧠 — navigator/gp.py: real GaussianProcessRegressor + UCB acquisition, fit on the real 4-point sweep — correctly ranks frac=0.5 above frac=0.3 (matches the real outcomes) — 2/2 tests
- ✅ **P5.4** Bug Gym + Medic · ★★★★ · 🔵 · 🔥 🧠 — medic/signatures.py + classifier.py: 6 regex rules (oom/unknown_kit/nan/cuda_error/network/missing_file) — 5/5 tests
- ✅ **P5.5** Selector · ★★★ · 🔵 · 🧠 — selector/thompson.py: Beta-Bernoulli Thompson sampling, converges to the better agent over 200 simulated outcomes — 3/3 tests
- ✅ **P5.6** Scout · ★★★ · 🔵 · 🧠 — scout/coverage.py: capability-gap detection + a repeat-request threshold before recommending a spawn — 3/3 tests
- ✅ **P5.7** Compute Router · ★★ · 🔵 · 🧠 — router/placement.py: local/Kaggle/Colab rule set, encodes the [MEASURED] '3rd concurrent job is slower' fact — 5/5 tests
- ✅ **P5.8** Analysts · ★★★ · 🔵 · 🧠 — analysts/grok_signature.py: detects the real train-saturates-then-test-transitions shape on an ACTUAL captured run (train sat. step 400, test transition step 2800) — 3/3 tests
- ✅ **P5.9** labml CLI, registry, reports, W&B · ★★ · 🔵 · 🔑 — cli.py `labml train-all`: trains/reports every model, ran for real -> var/reports/labml.json — 1/1 test

## P6

- ✅ **P6.1** Policy & approvals · ★★★ · 🔵 — policy.py: ApprovalPolicy + ApprovalStore (request/decide/expire-to-default) — 6/6 tests
- ✅ **P6.2** Spawn · ★★★ · 🔵 · 🔑 — spawn.py: real Groq call drafts a validated AgentSpec for a real coverage gap (ADAS-style, stepping-stone agents + past spawns in the prompt) — 1/1 (real LLM call)
- ✅ **P6.3** Refine (GEPA-lite) + shadow eval · ★★★★★ · 🟣 · 🔑 — lifecycle.py triggers (real Beta-posterior/Jaccard math) + refine.py: real Groq reflection call rewrites a prompt from traces, decide_promotion enforces the Pareto rule (mean +0.05, no task regresses >0.1) — 4/4 incl. real LLM call. Shadow-eval's *replay* (vs just the decision math) needs P4.6/P4.7's task-replay infra — not built yet, noted honestly
- ✅ **P6.4** Merge & retire · ★★★ · 🔵 · 🔑 — merge.py: real Groq synthesis call unions two agents' specs, decide_merge enforces 'merged >= max(parent) - 0.03' — 3/3 incl. real LLM call
- ✅ **P6.5** Reward v2 & feedback · ★★ · 🔵 — reward_v2.py: the full §6.9 formula (Q/S/T/C + optional human feedback) — 7/7 tests
- ✅ **P6.6** Lifecycle simulation test · ★★★ · 🔵 — the full lifecycle simulation: spawn -> refine -> merge -> retire against a REAL labd instance with REAL Groq calls for every generative step, events published and verified in order — 1/1 (flaky only on Groq's own transient 503 'over capacity' errors, confirmed by rerunning standalone — not our bug, see note on P4.10)

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
- 🟡 **P8.5** Panels II · ★★★ · 🔵 — only one panel built (jobs); a separate agent/roster panel is not started

## P9

- ⬜ **P9.1** Asset pipeline · ★★★ · 🔵 — no asset pipeline (assets/build_atlases.py) built — sprites exist on disk (assets/vendor/showdown) but aren't packed into Phaser atlases yet
- ⬜ **P9.2** Region map · ★★★ · 🔵 — no region map scene
- ⬜ **P9.3** Lab interior · ★★★ · 🔵 — no lab interior scene
- 🟡 **P9.4** Agent entities · ★★★ · 🔵 — game/world/stations.ts: the real capability->station mapping from §9.4.2 — 4/4 tests. No AgentEntity/grid-engine wiring yet
- ✅ **P9.5** The Director · ★★★★★ · 🟣 — game/director/director.ts: per-entity FIFO queues + the real-time-bound compression rule (walks collapse to a teleport, only the latest bubble survives, battle turns aggregate) + overlay-queue-to-toast — 7/7 tests. Bug found+fixed: re-compressing an already-compressed battle_turn task recomputed from raw deltaPct and silently dropped earlier history; fixed by having compressed tasks carry their own aggregate forward
- ⬜ **P9.6** Gym scene · ★★★★ · 🔵 — no Phaser scene actually renders yet — Director is pure logic, untested against a real Phaser canvas
- ⬜ **P9.7** Overlays & audio · ★★★ · 🔵 — not started
- ⬜ **P9.8** Binding audit · ★★ · 🔵 — not started — nothing to audit yet since nothing renders

## P10

- ✅ **P10.1** Remote runner protocol · ★★ · 🔵 — remote/dispatch.py: one shape for every backend (local/Colab/Kaggle all emit the same protocol lines), labml's Compute Router decides which — 3/3 tests
- ✅ **P10.2** Kaggle runner · ★★★ · 🔵 · 🔑 🔥(remote) — remote/kaggle_runner.py: real kaggle kernels push/status/output round trip. Bug found+fixed: Kaggle's kernel log is its own JSON-array wrapper around stdout chunks, not raw JSON-lines — looked right at a glance, wasn't; caught by actually reading the downloaded file. 2/2 tests against a real captured log
- ✅ **P10.3** Colab runner · ★★★ · 🔵 · 🔑 🔥(remote) — remote/colab_runner.py: real `colab run` round trip on a fresh free VM, confirmed it actually ran remotely (returned a different kernel version than this machine) — 1/1 real test, ~11-20s
- 🟡 **P10.4** Pokégear PWA · ★★★ · 🔵 — manifest.json + an /m shell page — no icons, no pairing/approve/redirect wiring yet
- ✅ **P10.5** Voice redirect · ★★ · 🔵 · 🔑 — voice.py: a real call to Groq's Whisper endpoint (multipart upload, auth, JSON response) — 1/1 real test. Accuracy untested (no real speech sample available in this environment, only a test tone) — the plumbing is proven, transcription quality is not
- ✅ **P10.6** Tunnel & view links · ★★ · 🔵 · 🌐 — scripts/tunnel.sh: a real cloudflared tunnel (--protocol http2, per the earlier measured QUIC-timeout finding) proxying actual HTTP traffic from a public trycloudflare.com URL to a running labd — verified with a real curl through the tunnel

## P11

- ⬜ **P11.1** Distillation (Edge) · ★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P11.2** Tiny NeRF (3D) · ★★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P11.3** Materials (Matbench) · ★★★ · 🔵 · 🧠 — 
- ⬜ **P11.4** Comparison arena · ★★★ · 🔵 · 🧠 — 
- ⬜ **P11.5** Oracle/Navigator per kit · ★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P11.6** Four-gym run · ★★★ · 🔵 · 🔥 — 

## P12

- ⬜ **P12.1** Doctor complete · ★★ · 🔵 — 
- ⬜ **P12.2** Chaos drills · ★★★ · 🔵 — 
- ⬜ **P12.3** Performance instrumentation · ★★★ · 🔵 — 
- ⬜ **P12.4** Acceptance suite · ★★★ · 🔵 · 🔥 — 
- ⬜ **P12.5** README & credits · ★ · 🔵 — 
- ⬜ **P12.6** Rehearsals · ★★ · human · 🔥 — 
