# PokéLab — PROGRESS

> One line per sub-phase. Status: ⬜ todo · 🟡 in progress · ✅ done · ❌ blocked. Add the key number when done (e.g. `✅ 62 s to 95% test acc`).
> Rule (Part 13.0.5): update this file and commit after every sub-phase.


## P0

- ✅ **P0.1** Repo & workspace skeleton · ★ · 🔵 — repo tree + README + justfile created
- ✅ **P0.2** Python env · ★ · 🔵 · 🌐 — uv venvs for brain/labml/workers, each installs + pytest runs
- ⬜ **P0.3** Node & web fork · ★ · 🔵 — 
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
- ✅ **P1.7** Supervisor, CLI, replay, doctor · ★★★ · 🔵 — `labd doctor` (GPU/power/disk/assets/datasets/venv/env checks, real against this machine) + `labd up`/`labd replay <db>` CLI via clap — 1/1 test

## P2

- ✅ **P2.1** Worker runtime · ★★ · 🔵 — pool_main.py warm worker entrypoint — spec-exact ready/job/metric/log/done protocol
- ✅ **P2.2** Kit interface + `smoke` kit · ★★ · 🔵 — KitSpec + `smoke` kit, 3/3 pytest + proven through the real Rust pool
- ✅ **P2.3** Grokking kit — models & data · ★★★ · 🔵 · 🔥 — ported from scripts/reference/grokbench/grok.py (transformer+MLP), unchanged training logic
- 🟡 **P2.4** Grokking telemetry hooks · ★★★ · 🔵 · 🔥 🧠 — basic train/test acc+loss streamed live; weight-norm/Fourier analysis (the deeper telemetry) not ported yet
- ✅ **P2.5** Kit benchmark & pool sizing · ★★ · 🔵 · 🔥 — real run: 96.5% test acc in 12.9s (frac=0.5) and a Rust-driven run groks to 95% in 17.1s wall — matches §11.1 budget order of magnitude
- ✅ **P2.6** W&B offline logging · ★ · 🔵 · 🔑 — offline W&B logging (no key reaches the worker) + scripts/wandb_sync.sh pushes with the key from .env — 3 real runs now live on wandb.ai/.../pokelab

## P3

- 🟡 **P3.1** Measure the gateway · ★ · 🔵 · 🔑 — Groq measured for real: openai/gpt-oss-20b ~0.3s, 1000 req/day + 8000 tok/min per ORG (not per key); Elevate not measured live — ELEVATE_TEAM_API_KEY still not provided, provider is code-complete but untested
- ✅ **P3.2** Bus client & state projection · ★★★ · 🔵 — bus.py (WS client to /internal/brain) + state.py (event-fold projection) — real test: brain submits a smoke job through a REAL labd subprocess, projects job.metric/job.done correctly, 1/1
- ✅ **P3.3** LLM router · ★★★★ · 🟣 · 🔑 — router.py: ordered fallback, per-provider sliding-window limiter, daily budget (brain.db), cache (llm_cache.db) — 4/4 tests incl. a real Groq call through the full router with budget recorded
- ✅ **P3.4** JSON I/O & repair · ★★ · 🔵 — jsonio.py: fenced/prose-wrapped JSON extraction + trailing-comma repair — 7/7 tests
- 🟡 **P3.5** Brain main & supervision · ★★ · 🔵 — main.py: reconnect-with-backoff loop against real labd, survives a labd restart without crashing (1/1) — full event-for-event replay-equivalence check deferred to P4 (needs real brain-side state to diff)

## P4

- ⬜ **P4.1** Paper ingestion · ★★★ · 🔵 — 
- ⬜ **P4.2** PaperPack extraction · ★★★★ · 🔵 · 🔑 — 
- ⬜ **P4.3** Specs, roster & tools · ★★★ · 🔵 — 
- ⬜ **P4.4** Agent runtime + action protocol · ★★★★★ · 🟣 · 🔑 — 
- ⬜ **P4.5** Capability analysis · ★★★ · 🔵 · 🔑 — 
- ⬜ **P4.6** Planner + templates · ★★★★ · 🔵 · 🔑 — 
- ⬜ **P4.7** Scheduler + verifiers · ★★★★ · 🟣 — 
- ⬜ **P4.8** Reward v1 · ★★ · 🔵 — 
- ⬜ **P4.9** Comparator v1 · ★★★ · 🔵 · 🔑 — 
- ⬜ **P4.10** **Vertical slice** · ★★★★ · 🔵 · 🔥 🔑 — 

## P5

- ⬜ **P5.1** Curve library sweep · ★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P5.2** Oracle (gbm + seq + param) · ★★★★★ · 🟣 · 🔥 🧠 — 
- ⬜ **P5.3** Navigator · ★★★★ · 🟣 · 🧠 — 
- ⬜ **P5.4** Bug Gym + Medic · ★★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P5.5** Selector · ★★★ · 🔵 · 🧠 — 
- ⬜ **P5.6** Scout · ★★★ · 🔵 · 🧠 — 
- ⬜ **P5.7** Compute Router · ★★ · 🔵 · 🧠 — 
- ⬜ **P5.8** Analysts · ★★★ · 🔵 · 🧠 — 
- ⬜ **P5.9** labml CLI, registry, reports, W&B · ★★ · 🔵 · 🔑 — 

## P6

- ⬜ **P6.1** Policy & approvals · ★★★ · 🔵 — 
- ⬜ **P6.2** Spawn · ★★★ · 🔵 · 🔑 — 
- ⬜ **P6.3** Refine (GEPA-lite) + shadow eval · ★★★★★ · 🟣 · 🔑 — 
- ⬜ **P6.4** Merge & retire · ★★★ · 🔵 · 🔑 — 
- ⬜ **P6.5** Reward v2 & feedback · ★★ · 🔵 — 
- ⬜ **P6.6** Lifecycle simulation test · ★★★ · 🔵 — 

## P7

- ⬜ **P7.1** Comparator v2 — diagnostics · ★★★ · 🔵 · 🔥 🔑 — 
- ⬜ **P7.2** Notes & reports · ★★ · 🔵 — 
- ⬜ **P7.3** Memory — lessons & Pokédex · ★★★ · 🔵 — 
- ⬜ **P7.4** Discovery · ★★ · 🔵 · 🌐 — 
- ⬜ **P7.5** Dataset & repo inputs · ★★★ · 🔵 — 
- ⬜ **P7.6** Author email drafts · ★ · 🔵 · 🔑 — 

## P8

- ⬜ **P8.1** Net & store · ★★★ · 🔵 — 
- ⬜ **P8.2** Static export served by labd · ★★ · 🔵 — 
- ⬜ **P8.3** Layout & HUD · ★★ · 🔵 — 
- ⬜ **P8.4** Panels I · ★★★ · 🔵 — 
- ⬜ **P8.5** Panels II · ★★★ · 🔵 — 

## P9

- ⬜ **P9.1** Asset pipeline · ★★★ · 🔵 — 
- ⬜ **P9.2** Region map · ★★★ · 🔵 — 
- ⬜ **P9.3** Lab interior · ★★★ · 🔵 — 
- ⬜ **P9.4** Agent entities · ★★★ · 🔵 — 
- ⬜ **P9.5** The Director · ★★★★★ · 🟣 — 
- ⬜ **P9.6** Gym scene · ★★★★ · 🔵 — 
- ⬜ **P9.7** Overlays & audio · ★★★ · 🔵 — 
- ⬜ **P9.8** Binding audit · ★★ · 🔵 — 

## P10

- ⬜ **P10.1** Remote runner protocol · ★★ · 🔵 — 
- ⬜ **P10.2** Kaggle runner · ★★★ · 🔵 · 🔑 🔥(remote) — 
- ⬜ **P10.3** Colab runner · ★★★ · 🔵 · 🔑 🔥(remote) — 
- ⬜ **P10.4** Pokégear PWA · ★★★ · 🔵 — 
- ⬜ **P10.5** Voice redirect · ★★ · 🔵 · 🔑 — 
- ⬜ **P10.6** Tunnel & view links · ★★ · 🔵 · 🌐 — 

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
