# PART 11 — NON-FUNCTIONAL DESIGN

## 11.1 Performance budgets (what "never buffer" means in numbers)

| Path | Budget | How we meet it |
|---|---|---|
| Event → visible on screen (local) | p95 < 150 ms | single-writer group commit ≤ 10 ms; WS fan-out; reducers O(1); Director per-entity queues |
| Human command → acknowledged | < 300 ms | labd persists + acks before the brain acts |
| Kit job submit → first training step | **8–10 ms warm** (AC) / 12–24 ms (battery) · 1.8–2.0 s cold (AC) `[MEASURED]` | warm pool with a prewarm dummy step (§5.5.3) |
| ML decision (Selector/Medic/Oracle predict) | ≤ 5 ms | in-process numpy/sklearn |
| Navigator batch suggestion | ≤ 50 ms | 43 ms GP fit + 4 ms prediction `[MEASURED]` |
| LLM call | p50 2–4 s, p95 8 s `[MEASURED range]` | masked: the agent's station animation + "…" bubble + other agents keep moving; Groq for anything interactive |
| Hero reproduction (grokking, Nanda config, GPU) | ~62 s to 95 % test acc `[MEASURED, plugged in]` | runs while other parts of the story continue |
| What-if runs | grok-MLP to 99 %: **4.0 s alone, 7.2 s each with 2 concurrent** (AC) · transformer frac 0.5: 14 s `[MEASURED]` | ≤ 2 concurrent GPU jobs; hero run alone |
| Client initial load | < 2.5 s | static export, atlases < 15 MB |
| Brain crash → resumed | < 10 s | snapshot + replay (§6.12) |
| Game frame rate | ≥ 55 fps with 12 agents + 3 battles | atlases, no per-frame allocs |

## 11.2 Reliability — failure modes and responses

| Failure | Detection | Response | User sees |
|---|---|---|---|
| brain crashes | labd sees socket close / process exit | restart with backoff; state rebuilt | "Oak is thinking…" banner ≤ 10 s |
| Worker crashes / CUDA error | EOF on stdout / exit code | job failed with signature → Medic; slot respawned | Pokémon hurt → Pokémon Center |
| GPU OOM | error class `oom` | Medic rule: halve batch/model width, retry once; else route to Kaggle | retry visible |
| Elevate 429 | HTTP 429 + Retry-After | circuit open, route to next provider; adaptive bucket | maybe a slower bubble; no failure |
| Elevate daily quota | 403 | all Elevate routes → Groq; HUD warns | "Elevate quota used — Groq mode" |
| Network down | provider errors + `doctor` probe | LLM cache; Groq off too → `llm-replay` mode for cached prompts; new prompts queue | HUD: OFFLINE; GPU work continues |
| labd crash | (it's the supervisor) | run under `just up` loop wrapper (`until labd up; do sleep 1; done`); WAL guarantees no torn writes | brief reconnect in the browser |
| Disk low | doctor + 1 Hz check | stop background sweeps < 3 GB free; refuse new artifacts < 1 GB | warning |
| Laptop on battery | telemetry | power warning (GPU 3× slower) | 🔌 banner |
| Phone can't reach laptop | pairing fails | fall back: hotspot LAN (laptop on the phone's hotspot) → cloudflared tunnel → desk approves | — |
| A demo step misbehaves live | human judgement | REPLAY mode of the recorded rehearsal session, labelled | REPLAY badge |

## 11.3 The network plan `[MEASURED 10 Oct]`

- **Campus Wi-Fi (SVKM-NMIMS FortiGate)** blocks category "Games" (e.g. `pokemonshowdown.com` → certificate replaced by Fortinet's). GitHub raw, PyPI, the Elevate gateway, Kaggle and Colab worked.
- **Phone hotspot** reached everything but had **1.6 s RTT** during one evening test (TLS handshakes timed out).
- Therefore: **everything is pre-downloaded** (sprites, cries, datasets, paper PDFs, fastembed model, PyTorch wheels, npm packages) — `just fetch` on a good connection, verified by `just doctor` (hash checks).
- Runtime internet is needed only for LLM calls (cached), Kaggle/Colab (optional), W&B sync (deferred) and arXiv discovery (cached).
- Timeouts: connect 5 s, read 45 s for LLMs; retries with jitter; never block the UI thread on the network.
- Phone connectivity order: (1) same LAN (desk on venue Wi-Fi or on the phone's hotspot; phone opens `http://<laptop-ip>:7700/m`), (2) `cloudflared tunnel --no-autoupdate --protocol http2 --url http://127.0.0.1:7700` — ⚠️ QUIC timed out on our network, `http2` works and **WebSockets pass through** (`✓run`: 1.3 s connect, 12 ms RTT via the Mumbai edge); the hostname is random and **changes on every start** (re-show the QR); a `~/.cloudflared/config.yaml` silently disables quick tunnels; ngrok free gives one stable domain if needed. (3) desk-only approvals. Note: a plain-HTTP LAN address is **not a secure context** — the phone UI and WebSockets work, but PWA install/web push need the HTTPS tunnel.

## 11.4 Security & safety

- Secrets only in `.env` (labd → brain). Workers, script jobs and remote kernels never receive keys. Logs redact `Authorization` headers and anything matching key patterns.
- Agent-written code runs as a separate process with `cwd` = its workspace, scrubbed env, wall-clock limit, no secrets; `env.install` only from an allowlist (torch, torchvision, numpy, scipy, scikit-learn, pandas, matplotlib, pymatgen, matminer, timm, einops, tqdm, pyyaml) — anything else needs human approval. (Not a hard sandbox — documented as a known limit.)
- Path traversal checks on every file endpoint (`canonicalize` + prefix check).
- WebSocket `Origin` check + cookie auth (CORS does not cover WebSockets); pairing codes travel in the URL fragment (§5.8).
- Remove `NODE_TLS_REJECT_UNAUTHORIZED=0` from the shell profiles (found during verification; it disables TLS verification for all Node processes).
- Phone tokens HMAC-signed, 24 h expiry, HttpOnly; pairing codes single-use, 5 min; `view` role cannot send commands.
- The Elevate key is shared across the team: never in the browser bundle, never in a repo, never in screenshots (the console masks it).

## 11.5 Observability

- **Logs:** `var/logs/labd.jsonl` (tracing), `var/logs/brain.jsonl` (structlog), `var/runs/<job>/stderr.log`. `just logs` tails all with colours.
- **The event log is the trace:** every decision event carries `causation` (the seq that caused it) → the console can show a decision's causal chain ("why did Oak spawn Eevee?" → coverage event → capability analysis → request).
- **Metrics endpoint** `GET /api/metrics` (Prometheus text): events/s, WS clients, queue depths, job counts, LLM latency histograms, cache hit rate.

## 11.6 Weights & Biases (the professional experiment record)

- Every kit run logs to W&B project `pokelab` (entity = the user's account) with config, the same metrics stream, final summary, and artifacts (curves, analysis PNGs) — group = project id, job type = kit, tags = source (live/library/bug_gym/diagnostic).
- **Offline-first:** workers run with `WANDB_MODE=offline` (writes `var/wandb/`); a background `wandb sync` task in labd pushes when the network allows. A W&B outage can never stall a run. 🔑 needs `WANDB_API_KEY` (§13.0.4).
- labml training (`just labml`) logs model CV metrics and the learning-over-time curves to W&B too; the console's Lab Brain panel links to the runs.
- We do **not** depend on W&B for the live UI — our own charts are primary (local, fast, offline-safe).

## 11.7 Testing strategy

| Layer | Tool | Must-have suites |
|---|---|---|
| Contracts | pytest + vitest(ajv) + cargo test | every fixture validates in all 3 languages |
| labd | cargo test | §5.11 list (store, LTTB, parser fuzz, kill tree, resync, fake-worker e2e) |
| brain | pytest(+asyncio, hypothesis) | protocol parser (40 recorded replies + fuzz), router (mock providers: 429/403/timeouts/Groq UA), scheduler on a fake plan, reward math, lifecycle triggers, crash-recovery replay equivalence |
| labml | pytest | Thompson update math; GP fit sanity; Oracle on a synthetic sigmoid family; Medic on a fixed failure set; deterministic seeds |
| workers/kits | pytest (CPU tiny configs) | each kit: 50-step smoke on CPU < 10 s emits valid lines, honours stop within 2 s |
| web | vitest + Playwright | reducers, Director compression, turn synthesis; replay e2e; phone pairing flow |
| System | `tests/e2e/` (pytest drives labd+brain with a fake LLM) | "reproduce grokking" project end-to-end with recorded LLM replies (`llm-replay`) in < 3 min |
| Chaos drills (P12) | scripts | kill brain mid-project; kill a worker mid-run; drop network; 429 storm; disk-full simulation |

---
