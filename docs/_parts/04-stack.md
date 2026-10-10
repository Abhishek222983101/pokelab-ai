# PART 4 — TECHNOLOGY STACK & REPOSITORY

## 4.1 Three languages, each where it is strongest `[DECISION D-04]`

| Language | Owns | Why this language here | Why not elsewhere |
|---|---|---|---|
| **Rust** (`core/`, binary `labd`) | Gateway, event store, job engine & process supervision, metrics pipeline, telemetry, auth | Long-lived, always-on process that must never stutter: no GIL, no GC pauses; tokio fans out thousands of WS messages/s with bounded per-client queues; `tokio::process` + process groups give clean kill semantics; ~15 MB RSS next to multi-GB torch workers; a single static binary that starts in milliseconds and supervises everything else | Writing ML or LLM orchestration in Rust would mean re-implementing PyTorch/numpy/sklearn ecosystems — slower to build, no speed gain (GPU kernels and network latency dominate there) |
| **Python 3.12** (`brain/`, `labml/`, `workers/`, `contracts/`) | Meta-controller, agents, LLM router, papers, memory, ML layer, training kits, remote runners | PyTorch (cu130 wheels verified on the RTX 5050), numpy/scipy/sklearn/optuna, fastembed, PyMuPDF, Kaggle & Colab CLIs, W&B — the ecosystem *is* Python. Every ML decision runs in-process in microseconds-to-milliseconds | Not for the gateway: the GIL + asyncio under heavy metric fan-out would make the UI stutter exactly when a demo is busiest |
| **TypeScript** (`web/`) | Game (Phaser), console (React), phone PWA | The browser runtime; reuses the PokeStonks engine, art pipeline, audio engine, menus and polish wholesale | — |

Interop is deliberately boring: **JSON over WebSocket/HTTP** between web ⇄ labd ⇄ brain, **JSON lines over stdin/stdout** between labd ⇄ workers. No gRPC, no message broker, no Docker — fewer moving parts on a single demo laptop. `[DECISION D-12]`

## 4.2 Verified environment (this laptop, 10 Oct 2026) `[MEASURED]`

| Item | Value |
|---|---|
| CPU / RAM | i5-13420H (8C/12T) · 15 GB RAM (≈ 4 GB free with a browser + IDE open — budget memory!) |
| GPU | RTX 5050 Laptop 8 GB (Blackwell, sm_120), driver 590.48, CUDA 13.1; power limit 75 W plugged in |
| Disk | **36 GB free** (90 % used) ⚠️ — one shared Python venv only (torch is ~3 GB); datasets ≤ 2 GB total |
| Rust | rustc / cargo **1.99.0** |
| Node / pnpm | **22.23.2** / **10.16.0** |
| Python | system 3.14 (do **not** use) → **uv 0.10.7** creates a **3.12** venv |
| PyTorch | **2.14.1+cu130** — works on sm_120 (the default PyPI wheel is the cu130 build) |
| SQLite (system) | 3.52.0 (Rust uses the bundled copy anyway) |
| Tools present | `cloudflared`, `just`, `make`, `kaggle` 2.2.4 (OAuth logged in), `colab` 0.7.4 (logged in), `exa` CLI |
| Power | On battery / Balanced the GPU is **~3× slower** (Nanda grokking: 181 s vs 62 s) — `labd doctor` warns |

## 4.3 The stack, layer by layer

> Versions below were **verified on 10 Oct 2026** (registries + compiled/run on this laptop — `✓run`). The lockfiles (`Cargo.lock`, `uv.lock`, `pnpm-lock.yaml`) become the pins in P0; record the resolved versions in `docs/PROGRESS.md`.

### 4.3.1 `core/` — Rust (rustc 1.99; all compiled together `✓run`)

| Crate · version | Use | Notes / gotchas |
|---|---|---|
| `tokio` 1.53 (full) | runtime, processes, timers, `broadcast` | `broadcast::Receiver` returns `RecvError::Lagged(n)` for slow subscribers — handle it (resync), never ignore it |
| `axum` **0.8.9** (`ws`, `macros`) | HTTP + WebSocket | ⚠️ routes are `/{id}` (old `/:id` panics); **copy examples from tag `axum-v0.8.9`, not `main`** (main holds unreleased 0.9 breaking changes); `ws.max_message_size(1<<20).on_upgrade(…)`; `Message::Text(Utf8Bytes)`; no `WebSocket::close` (send a Close frame) |
| `tower-http` **0.7.1** (`cors,fs,compression-gzip,compression-br,trace`) | `ServeDir` for `web/out`, compression, tracing | ⚠️ **CORS does not protect WebSockets** — check `Origin` in the WS handler (§5.8); 0.7 returns 404 for file paths with a trailing slash |
| `rusqlite` **0.40.2** (`bundled`, SQLite 3.53) + `tokio-rusqlite` 0.8 (reads) | the event store | `[DECISION]` rusqlite over sqlx (sqlx 0.9 cannot link next to rusqlite and multi-writer pools hit `SQLITE_BUSY`). `✓run` **940 k events/s** in 500-row transactions; **1.1 ms** to replay 5 000 rows from a seq |
| `serde` / `serde_json` 1.0.151 (`raw_value`) + `tokio-util` 0.7 `LinesCodec` | envelopes & worker lines | `✓run` **7.5 M METRIC lines/s** on one core (release build) — no SIMD parser needed; ⚠️ use `LinesCodec::new_with_max_length(256 << 10)` (unbounded `lines()` can exhaust memory); set `[profile.dev.package."*"] opt-level = 3` (debug JSON is very slow) |
| `process-wrap` **10.0.1** (`tokio1`) + `nix` 0.31 (`signal,process`) | job process groups | `CommandWrap::with_new(…).wrap(ProcessGroup::leader()).wrap(KillOnDrop)`; `child.signal(SIGTERM)` = killpg `✓run` (killed bash + 2 sleeps + python). ⚠️ tokio's `kill_on_drop` alone kills only the direct child |
| `nvml-wrapper` **0.13.0** | GPU util/mem/power/temp | `✓run` on this RTX 5050 / driver 590.48 (init 5 ms; 4 queries ≈ 12 µs); ⚠️ `fan_speed(0)` errors here — skip it. Fallback: `nvidia-smi --query-gpu=… --format=csv,noheader,nounits -lms 500` |
| `tracing` 0.1.44 + `tracing-subscriber` 0.3.23 (`env-filter,json`) | logs | `var/logs/labd.jsonl` |
| `sysinfo` | child RSS / host RAM | recycle workers at RSS > 3 GB |
| `schemars` 1.2.2 | (optional) emit JSON Schema for the few Rust-owned types | add `#[schemars(title=…)]` on enum variants |
| `qrcode` 0.14.1 | pairing QR (SVG + terminal `unicode::Dense1x2`) | — |
| `rand` 0.10 + `sha2` 0.11 + `base64` | opaque device tokens (stored hashed) | no JWT needed on one laptop |
| `uuid` (v7) | time-ordered ids | `job_01J…` |
| `clap`, `toml`, `dotenvy`, `anyhow`, `thiserror` | CLI, config, errors | — |
| own `lttb.rs` (~40 lines) | downsampling | the `lttb` crate is unmaintained |

### 4.3.2 `brain/`, `labml/`, `workers/`, `contracts/` — Python 3.12 (one uv workspace, one venv; co-installed `✓run`)

| Package · version | Use | Notes / gotchas |
|---|---|---|
| `pydantic` 2.13.5 (or 2.14.0, released 8 Oct) | contracts, tool args, agent specs | source of truth for schemas (§10.1) |
| `openai` **3.28.0** SDK (uses `httpx2`) | one client for **Elevate and Groq** (`base_url` per provider) | construct with `max_retries=0` (our router owns retries), `default_headers={"User-Agent": "pokelab/1.0"}` — ⚠️ Groq's Cloudflare blocks default Python UAs (403 / 1010 `[MEASURED]`); openai 3.x requires `httpx2` clients (not `httpx`) |
| `websockets` **17.2** | brain ⇄ labd socket | ⚠️ `additional_headers=` (not `extra_headers`); since 15.0 it **auto-uses environment proxies — pass `proxy=None`** for localhost; `send(text=…)` is keyword-only |
| `orjson` 3.13 | JSON | the gateway's 48 KB cap is measured on `orjson.dumps(request)` bytes |
| `json-repair` 0.64 + `tenacity` 9.2 | repair LLM JSON / retries | `✓run` strips fences/prose, fixes trailing commas |
| `numpy` 2.5.3, `scipy` 1.18.1, `scikit-learn` 1.9.1 | labml | numpy brute-force KNN over 20 k×384 = **4.4 ms** `✓run` (faster than sqlite-vec — no vector DB needed) |
| `optuna` **5.0.0** | TPE baseline only (Navigator ablation) | ⚠️ 5.0 defaults: multivariate TPE + `constant_liar=True`; `GPSampler` needs torch and fails only at trial #11; keyword-only APIs |
| `fastembed` **0.9.0** (+ onnxruntime 1.31) | bge-small-en-v1.5 embeddings | ⚠️ default cache is `/tmp/fastembed_cache` (tmpfs → re-download after reboot): **set `FASTEMBED_CACHE_PATH=var/models/fastembed` and `HF_HUB_OFFLINE=1`**; `✓run` 7 ms/query, 67 MB model |
| `pymupdf4llm` **1.28.2** (+ `pymupdf`/`pymupdf-layout` exactly 1.28.2) | PDF → Markdown | layout mode found all headers on a test paper but costs **~0.55 s/page** — run in a process pool, `use_ocr=False`; AGPL (fine here) |
| `arxiv` **4.0.1** | discovery | ⚠️ 4.0 removed `Search.results()` and `download_pdf()` → use `Client().results(Search(…))` and fetch `pdf_url` yourself; ≤ 1 request / 3 s; synchronous → `asyncio.to_thread` |
| `wandb` **0.30.0** | tracking mirror | offline first; `wandb sync --yes <dirs>`; `run.url` is `None` offline |
| `torch` **2.14.1** (+ `torchvision`) | kits | the **default PyPI wheel is already the cu130 build** with sm_120 — no extra index needed; import 1.7 s `✓run` |
| `kaggle` 2.2.4, `google-colab-cli` 0.7.4 | remote runners | see §8.8 (⚠️ Colab `--timeout` defaults to **30 s**) |
| `structlog`, `pytest`, `pytest-asyncio`, `hypothesis` | logs, tests | — |
| ❌ PydanticAI / OpenAI Agents SDK / LangGraph / instructor | not used | they need native tool-calling (the gateway has none) and/or conflict with websockets 17 / openai 3 → **custom action loop** (§6.3) `✓run` |

### 4.3.3 `web/` — TypeScript (forked from `~/PokeStonks/apps/web`)

| Package · version | Use | Notes / gotchas |
|---|---|---|
| `next` **16.3.8** (bump from 16.3.5), `react` 19.2.8 | shell, static export | ⚠️ 16.3.8 fixes a High-severity SSRF + cache-poisoning advisories — bump since the app is reachable through a tunnel; read `node_modules/next/dist/docs/` before Next code; Turbopack is default |
| `typescript` **^5** (5.9.3) | — | ⚠️ `latest` on npm is now TypeScript 7 (native compiler) — keep `^5` |
| `phaser` **3.80.1** + `grid-engine` **2.45.0** — *exact pins, upgrade never during the hackathon* | game | ⚠️ grid-engine ≥ 2.45.4 wants Phaser 3.85+, 2.52 wants Phaser 4 (Phaser 4.2.1 is out — migration later). `import * as Phaser`; StrictMode ref-guard (done in `PhaserMount.tsx`). grid-engine 2.45: `addCharacter/removeCharacter`, `moveTo(id, pos, {algorithm:'A_STAR', noPathFoundStrategy:'CLOSEST_REACHABLE', pathBlockedStrategy:'WAIT'}).subscribe(({result}) => …)`, `GridEngineHeadless` for tests |
| `zustand` 5.0.15 | stores | pure reducers |
| `uplot` **1.6.32** (+ `uplot-react` 1.2.4) | live curves | canvas; 166 k points in 25 ms; `setData` at ≤ 10 Hz |
| `@xyflow/react` **12.12.0** + `@dagrejs/dagre` **3.1.1** | lineage tree, plan DAG | ⚠️ use `@dagrejs/dagre` 3 (ESM, typed), not `dagre` 0.8.5; dagre returns node **centres** (subtract w/2, h/2); import `@xyflow/react/dist/style.css` |
| `react-markdown` + `remark-gfm` (preview) · `@uiw/react-md-editor` 4.1.2 (optional editor) | notes & reports | editor via `next/dynamic(…, {ssr:false})` |
| `react-pdf` 11.0.0 (`pdfjs-dist` **6.3.289**) — optional | in-console PDF view | set `workerSrc` in the same module; `.npmrc`: `public-hoist-pattern[]=pdfjs-dist`; the Library's default view is the extracted text with highlighted claims |
| `qrcode.react` 4.2.0 | pairing QR | named export `QRCodeSVG` |
| Tailwind 4 | console styling | already configured |
| `vitest` 5.0.3, `@playwright/test` 1.64.0 | tests | test Phaser through state on `window`, not pixels |
| **Removed** from PokeStonks | `wagmi`, `viem`, `@colyseus/sdk`, `maplibre-gl`, `three`, `postprocessing`, `@pythnetwork/*`, `@tanstack/react-query`, `contracts-abi`, `game-core` | no blockchain, globe or Colyseus |

### 4.3.4 Assets & external services

| Item | Source | Where it lands |
|---|---|---|
| Battle sprites (Gen 1–2, animated + static, front/back) | Pokémon Showdown mirror (done, 42 MB) | `assets/vendor/showdown/` → atlases in `web/public/assets/gen/` |
| Walking sprites (8-dir walk/idle/sleep/attack/hurt) | PMDCollab/SpriteCollab on GitHub (`sprite/<dex4>/<Anim>-Anim.png` + `AnimData.xml`) — CC BY-NC 4.0, credits in `credits.txt` | `assets/vendor/pmd/<dex>/` → atlases |
| Overworld humans (Ash/Red, Oak, Nurse Joy, Bill, gym leaders, NPCs) | **pret/pokefirered** `graphics/object_events/pics/people/*.png` (real FireRed overworld sprites: 16×32 frames, 10-frame strip; right = flipX of left) | `assets/vendor/frlg/` → atlases |
| Cries | PokeAPI/cries (`cries/pokemon/latest/<dex>.ogg`) | `assets/vendor/cries/` → `web/public/assets/cries/` |
| Trainer portraits | Showdown `sprites/trainers/*.png` (done) | same pipeline |
| Tiles, characters, music, SFX | PokeStonks procedural engines (code, no files) | `web/app/game/art`, `web/app/game/audio` |
| LLMs | Elevate gateway (Luna, DeepSeek V4 Pro, GPT-5 Mini), Groq ×2 (gpt-oss-120b/20b, qwen3.8-27b, whisper-large-v3) | §6.5 |
| Remote GPUs | Kaggle T4 (30 h/week), Colab T4 (free) | §8.8 |
| Tracking | Weights & Biases (key from the user — §13.0.4) | §11.6 |

### 4.3.5 Machine hygiene found during verification (fix in P0)

- ⚠️ `~/.bashrc` and `~/.zshrc` export **`NODE_TLS_REJECT_UNAUTHORIZED=0`** — it disables TLS certificate checks for *every* Node process. Remove it (ask the user before editing their shell files).
- `/usr/bin/pnpm` is 10.28.2 but the project pins `pnpm@10.16.0` → `corepack enable`.
- Free disk ≈ 34 GB (91 % used): one venv (~4–5 GB with torch), no GROBID Docker image (15 GB).

## 4.4 Repository layout

```
~/elevate-ps03/                       # repo root (git init in P0.1; GitHub remote is the user's call)
├── README.md                         # how to run, architecture summary, licences, credits
├── justfile                          # all commands (§4.6)  — `just up`, `just doctor`, `just test`…
├── .env.example                      # every variable from §4.5, no values
├── .gitignore                        # var/, data/, assets/vendor/, web/public/assets/gen/, .venv/, target/, node_modules/, wandb/
├── docs/
│   ├── SYSTEM-ARCHITECTURE.md        # this document (built from docs/_parts by `just docs`)
│   ├── OVERVIEW.md                   # human-readable concept tour
│   ├── PROGRESS.md                   # one line per sub-phase: ✅/🟡/❌ + key number
│   └── decisions/                    # ADR-style notes for any change to a [DECISION]
├── config/
│   ├── lab.toml                      # ports, pool sizes, budgets, autonomy policy defaults
│   ├── llm.toml                      # providers, models, routes, limits (§6.5)
│   ├── roster.toml                   # base agents: species, role, capabilities, prompts ref
│   └── papers.toml                   # paper packs enabled for the demo
├── contracts/                        # SINGLE SOURCE OF TRUTH for cross-language types
│   ├── pokelab_contracts/            # Python package (pydantic models)
│   │   ├── envelope.py events.py commands.py jobs.py agents.py papers.py
│   │   └── export.py                 # → schemas/*.json
│   ├── schemas/                      # generated JSON Schema 2020-12 (committed)
│   ├── fixtures/                     # golden JSON examples, validated in all 3 languages
│   └── ts/                           # generated .d.ts → copied to web/app/lib/contracts/
├── core/                             # Rust workspace
│   ├── Cargo.toml
│   └── crates/
│       ├── labd/                     # binary: main.rs, config.rs, supervisor.rs, doctor.rs
│       ├── lab-store/                # event store, writer thread, readers, snapshots, metrics tables
│       ├── lab-gateway/              # axum routes, ws hub, cmd intake, static serving, auth/pairing
│       ├── lab-jobs/                 # scheduler, warm pool, process groups, JSON-lines parser, remote
│       ├── lab-metrics/              # ring buffers, LTTB, rollups
│       └── lab-telemetry/            # NVML / nvidia-smi, power profile, sysinfo
├── brain/
│   └── pokelab_brain/
│       ├── main.py                   # boot: connect, rebuild state, start loops
│       ├── bus.py state.py           # labd socket client; in-memory projection
│       ├── oak/                      # intake.py capabilities.py planner.py templates/ scheduler.py
│       │                             # selector_adapter.py lifecycle.py policy.py redirect.py
│       ├── agents/                   # spec.py runtime.py protocol.py context.py verifiers.py
│       │   ├── tools/                # paper.py memory.py code.py env.py jobs.py analysis.py notes.py
│       │   │                         # human.py discover.py data.py repo.py finish.py
│       │   └── prompts/              # role prompts (markdown, versioned)
│       ├── llm/                      # router.py providers.py ratelimit.py cache.py jsonio.py budget.py
│       ├── papers/                   # ingest.py sections.py claims.py packs.py arxiv.py
│       ├── memory/                   # pokedex.py dedup.py lessons.py fixes.py embed.py
│       ├── science/                  # comparator.py checklists/ diagnostics.py reports.py notes.py
│       └── reward.py snapshot.py
├── labml/
│   └── pokelab_labml/
│       ├── oracle/                   # features.py gbm.py seq.py calibrate.py library.py
│       ├── navigator/                # gp.py acquisition.py space.py
│       ├── selector/                 # thompson.py contextual.py priors.py
│       ├── medic/                    # normalize.py signatures.py classifier.py
│       ├── scout/                    # coverage.py clusters.py merge.py
│       ├── router/                   # runtime_model.py placement.py
│       ├── analysts/                 # grok_fourier.py nerf_spectrum.py kd_darkknowledge.py materials_parity.py
│       ├── registry.py               # versioned model files under var/labml/
│       └── cli.py                    # `labml train-all`, `labml eval` → var/reports/*.json
├── workers/
│   └── pokelab_workers/
│       ├── pool_main.py              # warm worker entrypoint
│       ├── protocol.py emit.py stop.py
│       ├── kits/                     # grokking/ distill/ nerf/ materials/ arena/ smoke/  (each: spec.py run.py analyze.py)
│       ├── script_runner.py          # wraps agent-written scripts
│       └── remote/                   # kaggle_runner.py colab_runner.py templates/
├── web/                              # Next 16 app (fork of PokeStonks apps/web, web3 removed)
│   └── app/
│       ├── page.tsx  m/page.tsx  replay/page.tsx
│       ├── lib/ (labSocket.ts api.ts contracts/ store/ format.ts)
│       ├── console/ (panels…)
│       └── game/ (PhaserMount.tsx scenes/ director/ world/ battle/ art/ audio/ sprites/)
├── assets/
│   ├── vendor/ (showdown/ pmd/ cries/)   # downloaded, gitignored
│   └── build_atlases.py              # GIF/PMD → Phaser atlases + manifest
├── scripts/                          # fetch_assets.sh fetch_datasets.sh fetch_papers.sh bench.sh demo_prep.sh
├── data/                             # datasets + paper PDFs (gitignored)
├── tests/                            # cross-component e2e (pytest + playwright)
└── var/                              # runtime state (gitignored): lab.db brain.db llm_cache.db runs/ notes/ logs/ labml/ reports/ wandb/
```

## 4.5 Configuration & secrets

`.env` (never committed; labd loads it and passes **only** what each child needs):

| Variable | Used by | Notes |
|---|---|---|
| `ELEVATE_TEAM_API_KEY` | brain | Elevate gateway bearer key (keep the `HideCopy` suffix out — see §14.3) |
| `GROQ_API_KEY_1`, `GROQ_API_KEY_2` | brain | fallback provider; 1000 req/day, 8000 tok/min per key `[MEASURED headers]` |
| `WANDB_API_KEY` | workers, labml | optional; offline mode if absent |
| `LABD_BRAIN_SECRET` | labd ⇄ brain | random 32 bytes, generated by `just init` |
| `LABD_PAIRING_SECRET` | labd | HMAC key for phone tokens |
| `KAGGLE` / `COLAB` | — | no env needed: CLIs use their own OAuth stores (`~/.kaggle`, colab config) |
| `POKELAB_MODE` | all | `live` (default) · `replay` · `llm-replay` (LLM cache only) |

⚠️ Workers and script jobs get a **scrubbed environment** (no API keys) — agent-written code never sees secrets.

## 4.6 Commands (`justfile`)

| Command | Does |
|---|---|
| `just init` | create `.env` from example, generate secrets, `uv sync`, `pnpm i`, `cargo build` |
| `just fetch` | assets, datasets, paper PDFs, fastembed model (🌐 hotspot if campus blocks) |
| `just atlases` | build Phaser atlases from vendor sprites |
| `just contracts` | export JSON Schemas, generate TS types, run contract fixture tests in all 3 languages |
| `just up` | build web export if stale, start `labd` (which starts brain + workers) on `:7700` |
| `just dev` | `labd` + `next dev` on `:3000` with proxy (hot reload) |
| `just doctor` | preflight: GPU, power mode, disk, assets, datasets, models, gateway reachability, quotas, ports, tunnel |
| `just test` | `cargo test` + `pytest` + `vitest` |
| `just e2e` | Playwright against a REPLAY fixture session |
| `just library` | 🔥 generate the curve library (Part 7.1.4) |
| `just labml` | train + evaluate all labml models → `var/reports/labml.json` |
| `just tunnel` | `cloudflared tunnel --url http://localhost:7700` and print the QR |
| `just replay <db>` | serve a recorded session in REPLAY mode |
| `just docs` | concatenate `docs/_parts/*.md` → `docs/SYSTEM-ARCHITECTURE.md` |

---
