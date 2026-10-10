# PART 5 — `labd`: THE RUST LAB CORE

`labd` is the lab's spine: it **stores** everything (events), **moves** everything (WebSocket fan-out), **runs** everything (jobs and child processes) and **watches** everything (metrics, GPU, power). It contains *no research logic* — it never decides what to run or which agent to use; the brain does. That keeps the Rust surface small (target ≈ 3–4 k LOC) and stable.

## 5.1 Crate responsibilities and boundaries

| Crate | Public surface | Depends on |
|---|---|---|
| `lab-store` | `Store::open(path)`, `append(Vec<NewEvent>) -> Vec<Seq>` (async via writer channel), `events_since(seq, limit)`, `snapshot_put/get`, `jobs_*`, `metrics_append(batch)`, `metrics_query(job, keys, max_points)` | rusqlite |
| `lab-metrics` | `SeriesBuffer` (ring, f32), `lttb(points, n)`, `Rollup` (1 Hz progress) | — |
| `lab-jobs` | `JobEngine::submit(spec)`, `kill(job, reason)`, `pool_status()`; emits `JobEvent`s on a channel | lab-store, lab-metrics, tokio::process |
| `lab-telemetry` | `Telemetry::sample() -> GpuSample, HostSample, PowerSample` (1 Hz task) | nvml-wrapper, sysinfo |
| `lab-gateway` | axum `Router`; `Hub` (topics, subscribers); command intake; auth | all of the above |
| `labd` | CLI (`up`, `doctor`, `replay`, `export`), config, supervisor of brain + pool | all |

## 5.2 Startup sequence (`labd up`)

1. Load `config/lab.toml` + `.env`; resolve paths under `var/`.
2. Open `var/lab.db` (create + migrate; WAL; `PRAGMA synchronous=NORMAL; foreign_keys=ON; busy_timeout=2000`).
3. Start the **writer thread** (§5.3) and the **telemetry task** (1 Hz).
4. Start the **job engine**; spawn the warm pool (`w-gpu-0..g`, `w-cpu-0..c`) and wait ≤ 10 s for each `{"t":"ready"}` (failure → mark slot degraded, keep going).
5. Bind `:7700` (HTTP, `/ws`, `/internal/brain`, static `web/out`).
6. Spawn **brain** (`.venv/bin/python -m pokelab_brain.main`) with `LABD_URL`, `LABD_BRAIN_SECRET`, LLM keys; restart with exponential backoff (1 → 30 s) if it exits.
7. Emit `lab.started {version, mode, gpu, power}`; print the URL + pairing QR (ASCII) to the terminal.

Target: **`labd` ready < 1 s; whole lab (brain connected, pool warm) < 8 s** `[TARGET]`.

## 5.3 Event store

**Schema** (full DDL in §10.4):

- `events(seq INTEGER PRIMARY KEY, ts TEXT, kind TEXT, v INT, project TEXT, actor TEXT, corr TEXT, causation INT, payload TEXT, display TEXT)` with indexes `(kind)`, `(project, seq)`, `(corr)`.
- `snapshots(name TEXT PRIMARY KEY, seq INT, payload TEXT)` — the brain posts `state.snapshot` every 200 events or 15 s.
- `jobs`, `metrics`, `artifacts` — projections that labd itself maintains because it runs the jobs.

**Writer thread (single writer, group commit):**
```
loop:
  first = rx.recv()                      // blocking
  batch = [first] + rx.try_recv up to 512 items or 10 ms deadline
  BEGIN IMMEDIATE
    for op in batch: INSERT … (seq assigned by SQLite rowid)
  COMMIT
  for op in batch: op.reply.send(seq)    // callers awaiting durability
  hub.publish(committed events)          // fan-out happens only AFTER commit
```
- **Durability before visibility:** clients never see an event that could be lost on crash.
- Metrics are batched separately (every 250 ms) into `metrics(job_id, key, step, value)` — `WITHOUT ROWID`, PK `(job_id, key, step)`.
- Throughput target **≥ 20 k events/s, p99 commit latency < 15 ms** `[TARGET]` (we need ~100/s).
- `labd export <dir>` copies `lab.db` (online backup API) for REPLAY fixtures; automatic backup every 10 min to `var/backups/` (keep 6).

**Event envelope** (Rust struct, mirrored from `contracts/envelope.py`):
```rust
pub struct Event {
    pub seq: i64,                 // assigned on commit
    pub ts: String,               // RFC3339 with ms, UTC
    pub kind: String,             // "agent.task_started"
    pub v: u16,                   // payload schema version
    pub project: Option<String>,  // "prj_01J…"
    pub actor: String,            // "oak" | "agent:<id>" | "human:<device>" | "system" | "job:<id>"
    pub corr: Option<String>,     // correlation id (task/job/proposal)
    pub causation: Option<i64>,   // seq of the event that caused this one
    pub payload: Box<RawValue>,   // opaque to labd except kinds it owns
    pub display: Option<Box<RawValue>>, // presentation hints (importance, bubble text) — never state
}
```

## 5.4 Gateway

### 5.4.1 HTTP routes

| Method & path | Auth | Purpose |
|---|---|---|
| `GET /api/health` | none | `{ok, mode, uptime_s, brain: up/down, pool: [...], gpu, power}` |
| `GET /api/bootstrap` | desk/phone/view | latest snapshot + events since it (≤ 5 000) + config subset + `me` (role) |
| `GET /api/events?since=&limit=&kind=&project=` | desk/view | paging the log (console "history") |
| `GET /api/jobs?project=&status=` · `GET /api/jobs/:id` | desk/view | job projection |
| `GET /api/jobs/:id/metrics?keys=a,b&max_points=600` | desk/view | LTTB-downsampled full history |
| `GET /api/artifacts/:job/:name` | desk/view | files from `var/runs/<job>/` (path-checked) |
| `GET /api/files/notes/*`, `PUT …` | desk (PUT), view (GET) | Markdown notes (writes become `cmd.note_save` events) |
| `GET /api/papers/:id/pdf` | desk/view | serve the stored PDF |
| `POST /api/cmd` | desk/phone | REST fallback for commands (same validation as WS) |
| `GET /api/pair` | **localhost only** | new pairing code + QR SVG (expires 5 min) |
| `POST /api/pair/claim {code}` | none | → device token (role `phone` or `view`), set as HttpOnly cookie |
| `GET /api/telemetry` | desk | last 120 s of GPU/host samples |
| `GET /` `/m` `/replay` `/assets/*` | none | static export of `web/` |

### 5.4.2 WebSocket `/ws` (clients)

```
client → {type:"hello", token?, since:<seq|null>, topics:["events","telemetry"], want_metrics:["job_…"]}
server → {type:"welcome", role, server_seq, mode}
server → {type:"event", e:<Event>}                         // ordered by seq, no gaps
server → {type:"metrics", job, points:[[step, {k:v}],…]}   // ≤ 10 Hz per job, coalesced
server → {type:"telemetry", gpu:{util,mem_mb,power_w,temp_c}, host:{ram_free_mb,cpu}, power:{ac,profile}}
client → {type:"sub", want_metrics:[…]} | {type:"cmd", id, cmd:"approve", args:{…}}
server → {type:"cmd_ack", id, ok, error?, seq?}
both   → {type:"ping"} / {type:"pong"} every 10 s (dead after 30 s)
```

**Fan-out order (no gaps, no duplicates):** on `hello`, the handler (1) subscribes to the broadcast hub *first*, (2) replays `seq > since` from SQLite, (3) forwards live events, skipping any `seq ≤ last_sent`. On `RecvError::Lagged` → send `{type:"resync", since:last_sent}` and replay again. ⚠️ Never copy axum's chat example loop (`while let Ok(m) = rx.recv()`), which silently drops lagging clients.

**Hub & backpressure:** each subscriber has a bounded queue (events 4 096, metrics 256). Metric frames are *coalesced* (only the latest frame per job kept) when the queue is full; if the *event* queue overflows, the server sends `{type:"resync", since}` and drops the subscriber's backlog — the client re-bootstraps. A slow phone can never slow the desk.

### 5.4.3 Internal socket `/internal/brain`

Header `Authorization: Bearer $LABD_BRAIN_SECRET`; only one brain connection at a time (newest wins).

```
brain → {type:"publish", events:[NewEvent…], req}            // labd commits, replies {type:"published", req, seqs}
brain → {type:"snapshot", name, seq, payload}
brain → {type:"job_submit", req, spec:JobSpec}               // labd → {type:"job_accepted", req, job_id, deduped_from?}
brain → {type:"job_kill", job_id, reason}
brain → {type:"subscribe", since}                            // brain also receives the full event stream
labd  → {type:"event", e}                                    // includes human commands and job events
labd  → {type:"job_metrics", job, points}                     // full-rate (not downsampled) for the Oracle
```

### 5.4.4 Command intake

Every human command is: authenticated (role) → schema-validated → persisted as an event (`human.*`) → forwarded to the brain. labd itself executes only infrastructure commands (`kill_job`, `pause_pool`, `resume_pool`); everything with research meaning (approve, redirect, feedback…) is decided by the brain. Role rules: `desk` = all; `phone` = approve/reject/redirect/kill/feedback/ask; `view` = read-only.

## 5.5 Job engine

### 5.5.1 Resource model & scheduling

| Resource | Default slots | Config key |
|---|---|---|
| `gpu` | **2** warm GPU workers — `[MEASURED]` a 2nd concurrent job adds only +11 % total throughput on AC and a 3rd *reduces* it (0.96×); each job is single-core-CPU-bound (94–115 % of one core) and each warm worker idles at **1.17 GB RSS + 226 MiB VRAM**, so host RAM, not VRAM, is the limit. The hero run gets the GPU alone (4.0 s vs 7.2 s each when two share it) | `pool.gpu_workers` |
| `cpu` | 1 (sklearn/numpy only — **no torch import**, ~0.15 GB) for materials/arena kits and analysts | `pool.cpu_workers` |
| `script` | 1 cold script job at a time | `pool.script_slots` |
| `kaggle` | 1 | `remote.kaggle_slots` |
| `colab` | 1 | `remote.colab_slots` |

Queue = priority heap per resource: `interactive (0) < project (1) < whatif (2) < background (3)`, FIFO within a priority. A higher-priority job never *preempts* a running one, except `background` jobs (curve-library sweeps) which receive `stop` and are re-queued from their last checkpoint when an interactive job waits > 2 s.

### 5.5.2 Dedup (the Pokédex fast path)

`config_hash = sha256(canonical_json({kit, kit_version, config, seed, dataset_version}))[:16]`. On submit, if a **completed** job with the same hash exists and the spec does not say `force: true`, labd answers immediately with `job.deduped {from_job}` and the brain emits `memory.hit`. `[PS-D15]` (AC-12)

### 5.5.3 Warm pool lifecycle

```
spawn  : .venv/bin/python -m pokelab_workers.pool_main --slot w-gpu-0 --device cuda:0
         env: CUDA_VISIBLE_DEVICES=0, OMP_NUM_THREADS=4, TQDM_DISABLE=1, PYTHONUNBUFFERED=1,
              TORCH_CUDNN_V8_API_LRU_CACHE_LIMIT=…, WANDB_MODE=offline, (no API keys)
prewarm: after import + CUDA init the worker runs ONE dummy 5-step training job (tiny MLP) —
         `[MEASURED]` without it the first real job still pays 0.9 s (AC) / 1.6 s (battery); with it,
         job receipt → first training step = 8–10 ms (AC), 12–24 ms (battery). Startup ≈ 2.0 s (AC).
ready  : worker prints {"t":"ready", torch, device, pid}
assign : labd writes {"t":"job", …} + "\n" to stdin
run    : stdout lines parsed; stderr captured into a 64 KB ring (for error signatures)
finish : {"t":"done"} → slot free; after 50 jobs or RSS > 3 GB → graceful restart
crash  : EOF/exit → job failed (error_sig from stderr tail) → respawn slot
```
- stdout **and** stderr are drained concurrently (a full 64 KB pipe blocks the worker); stdout via `LinesCodec` with a 256 KB max line.
- Every spawned process group id is recorded (`kv: pgid:<slot|job>`); on labd start, **orphaned groups from a previous crash are killed** before the pool starts (workers in their own group do not receive the terminal's Ctrl-C).

### 5.5.4 Kill semantics (`[PS-D20]`, Oracle early stop)

1. `{"t":"stop","job_id","reason"}` on stdin → the kit's `StopToken` is set → loop exits at the next step, emits `{"t":"done","status":"stopped"}` (target ≤ 2 s).
2. If no `done` within 5 s → `SIGTERM` to the process group; 3 s later `SIGKILL`; warm slot respawned.
3. Script jobs (no stdin protocol guarantee) go straight to step 2.

### 5.5.5 JSON-lines parsing & validation

- Lines > 256 KB are rejected (logged, not crashed). Non-JSON lines are treated as `log` lines (so `print()` debugging in agent scripts never breaks parsing).
- `metric.m` values must be finite numbers; NaN/Inf are kept as `null` *and* raise a `job.anomaly {kind:"nan"}` event (Medic signal).
- Every parsed line updates the job's ring buffers; persistence is batched (§5.3).

### 5.5.6 Timeouts and budgets

Every `JobSpec` carries `budget.max_seconds` (hard wall-clock) and optional `max_steps`. labd enforces wall-clock; kits enforce steps. Timeout → kill with reason `timeout` → `job.timeout`.

## 5.6 Metrics pipeline

- **Ring buffers** per `(job, key)`: last 20 000 points in memory (f32 step + f32 value).
- **To clients:** every 100 ms per active job, send only *new* points since the last frame, thinned by LTTB to ≤ 50 points per frame; clients append. On (re)subscribe, the client first fetches `/api/jobs/:id/metrics?max_points=600` (LTTB over full history) then appends live frames.
- **To brain:** full-rate points (the Oracle needs exact prefixes), batched every 250 ms.
- **Rollups:** 1 Hz `job.progress {step, frac_budget, last:{k:v}, steps_per_s}` events into the log (so REPLAY and late joiners have a coarse curve even without the metrics table).

LTTB (largest-triangle-three-buckets) is ~40 lines of Rust; unit-tested against a reference Python implementation on random walks (max deviation check).

## 5.7 Telemetry & the power guard

1 Hz: GPU util/mem/power/temp (NVML, fallback `nvidia-smi`), host RAM free/CPU, AC from `/sys/class/power_supply/A*/online`, profile from `powerprofilesctl get` (⚠️ on this Acer `/sys/firmware/acpi/platform_profile` returns an I/O error — use `powerprofilesctl`, fallback `/sys/devices/system/cpu/cpufreq/policy0/energy_performance_preference`). If AC is off or the profile is not `performance` while a GPU job runs → `lab.warning {kind:"power"}` → HUD shows **"🔌 Plug in + Performance mode (runs 3–3.5× slower)"**. `[MEASURED]` Our small GPU jobs are CPU-launch-bound: on battery the busiest core ran at 0.7–1.2 GHz vs 3.3–3.5 GHz on AC (grok-MLP 213 vs 746 steps/s).

## 5.8 Auth & pairing

- Desk: requests from `127.0.0.1` are role `desk` (single-user laptop).
- Phone: console shows a QR for `http(s)://<host>/m#pair=<code>` — the code sits in the URL **fragment**, which browsers never send to servers or tunnels; the page posts it to `/api/pair/claim`; code = 6 chars, single use, 5 min; claim → token `HMAC(secret, device_id|role|expiry)` in an HttpOnly cookie; valid 24 h.
- Collaborator: `view` role via a separate QR/link (read-only).
- Internal brain socket: shared secret.
- ⚠️ **CORS does not apply to WebSockets**: the `/ws` handler checks the `Origin` header (allow own origin / tunnel host) and the cookie; browsers cannot set `Authorization` on a WebSocket, but they do send same-origin cookies on the upgrade request.

## 5.9 REPLAY mode

`labd replay var/sessions/<name>.db --speed 1.0` serves the recorded event log with original inter-event timing (scaled), metrics included; commands are rejected with "replay mode". The HUD shows a permanent **REPLAY** badge. Used for (a) UI development without GPU/LLM, (b) the labelled offline fallback. `[PS-D27]` honesty rule: a replay is never presented as live.

## 5.10 `labd doctor` (preflight)

Checks and prints ✅/⚠️/❌: GPU visible + CUDA in the venv · power AC + profile · free disk > 5 GB · free RAM > 3 GB · ports free · `web/out` built · atlases built · datasets present (hashes) · paper PDFs present · fastembed model cached · labml models present · Elevate gateway reachable + one 10-token call · Groq reachable · Kaggle/Colab auth (`kaggle config view`, `colab sessions`) · W&B mode · tunnel binary. Exit code ≠ 0 on any ❌. Run before every rehearsal.

## 5.11 Tests (Rust)

| Test | Checks |
|---|---|
| `store_roundtrip` | append 10 k events from 8 tasks → seq strictly increasing, no gaps, readers see committed only |
| `writer_crash_safety` | kill -9 mid-batch (subprocess test) → reopen → no partial batch |
| `lttb_reference` | matches Python reference within tolerance |
| `jsonl_parser_fuzz` | random bytes/oversized/NaN lines never panic |
| `job_kill_tree` | fake worker spawning a grandchild → kill leaves no orphan PIDs |
| `ws_resync` | slow subscriber gets `resync`, fast subscriber unaffected |
| `fake_worker_e2e` | `tests/fake_worker.py` emits 10 k metrics → client receives ≤ 10 Hz frames, DB has all points |

---
