# PART 10 — CONTRACTS, DATA MODEL & PROTOCOLS

## 10.1 One source of truth across three languages `[DECISION D-10]`

```
contracts/pokelab_contracts/*.py  (Pydantic v2 — authoritative)
        │  python -m pokelab_contracts.export
        ▼
contracts/schemas/*.json  (JSON Schema 2020-12, committed)
        ├──► json-schema-to-typescript ──► contracts/ts/*.d.ts ──► web/app/lib/contracts/
        └──► Rust: hand-written serde structs for the ~12 types labd touches (Event envelope, JobSpec,
             worker lines, commands, telemetry) + `cargo test` validating every fixture in contracts/fixtures/
contracts/fixtures/*.json  ──► validated by pytest (pydantic), vitest (ajv), cargo test (serde round-trip)
```
`just contracts` regenerates and runs all three fixture suites; CI-style rule: **no contract change without a fixture**.

## 10.2 Event catalogue (kind → payload essentials)

| Kind | Emitted by | Payload (essential fields) |
|---|---|---|
| `lab.started` / `lab.warning` / `lab.mode_changed` | labd | version, mode, gpu, power / kind, message |
| `state.snapshot` | brain | (stored in `snapshots`, not in `events`) |
| `human.request` | labd (from cmd) | text, attachments[], device |
| `human.approval_requested` | brain | approval_id, kind (spawn/merge/remote/question), title, body, options, expires_at |
| `human.approved` / `human.rejected` / `human.expired` | labd / brain | approval_id, note?, device |
| `human.redirected` | labd | project, text, device |
| `human.feedback` | labd | target (task/report/agent), value (👍/👎/stars), note? |
| `human.note_saved` | labd | path, bytes, sha |
| `project.created` | brain | project_id, spec (ProjectSpec) |
| `project.plan_proposed` / `project.plan_approved` / `project.plan_revised` | brain | plan (steps[]), revision, diff? |
| `project.status` | brain | status, reason? |
| `project.badge_awarded` | brain | paper_id, verdict, evidence_ref |
| `paper.ingested` / `paper.pack_ready` / `paper.pack_corrected` | brain | paper_id, title, sections, claims[], spec, corrections? |
| `oak.capability_analysis` | brain | required[{cap, why, weight, new?}], coverage{}, gaps[] |
| `oak.selection` | brain | step_id, cap, candidates[{agent, alpha, beta, sample}], chosen, model_version |
| `oak.decision` | brain | what, why, inputs_ref (generic rationale record) |
| `agent.spawn_proposed` / `agent.spawned` | brain | proposal_id / agent spec, why, prior |
| `agent.task_assigned` / `agent.task_started` | brain | task_id, step_id, agent, cap, station |
| `agent.thought` | brain | task_id, text (≤ 140) |
| `agent.action` / `agent.action_result` | brain | task_id, tool, args_summary / ok, summary, duration_ms |
| `agent.task_completed` / `agent.task_failed` | brain | task_id, status, outputs_ref / error_class |
| `agent.rewarded` | brain | task_id, agent, Q, S, T, C, H, r, posterior{alpha,beta} |
| `agent.refine_proposed` / `agent.evolved` / `agent.refine_rejected` | brain | from, to?, delta, shadow_results[] |
| `agent.merge_proposed` / `agent.merged` | brain | parents[], child?, why |
| `agent.retire_proposed` / `agent.retired` | brain | agent, reason, posterior |
| `llm.call` | brain | agent?, route, provider, model, in_tok, out_tok, reasoning_tok, latency_ms, cached, status |
| `job.submitted` / `job.deduped` / `job.queued` / `job.started` | labd | job_id, spec_ref, config_hash, target, slot / from_job |
| `job.progress` (1 Hz) | labd | job_id, step, frac_budget, last{k:v}, steps_per_s |
| `job.forecast` | brain | job_id, p_success, eta_step{q10,q50,q90}, final{q10,q50,q90}, model_version |
| `job.anomaly` | labd | job_id, kind (nan/spike/stall) |
| `job.artifact` | labd | job_id, name, mime, bytes |
| `job.kill_requested` / `job.killed` | brain / labd | job_id, reason, gpu_s_saved? |
| `job.completed` / `job.failed` / `job.timeout` | labd | job_id, final{…}, wall_s, gpu_s / error_sig, etype, tail |
| `compute.route_decided` | brain | job_id, target, predicted{local,kaggle,colab}, why |
| `memory.hit` / `memory.lesson_saved` / `memory.fix_recalled` / `memory.fix_saved` | brain | refs, text, success_count |
| `ml.model_updated` | brain | model, version, n_train, metrics |
| `ml.navigator_updated` | brain | project, grid (coarse μ/σ), suggestions[] |
| `analysis.ready` | brain | job_ids, analyst, artifacts[] |
| `report.comparison_ready` | brain | project, verdicts[], hypotheses[], path |
| `notes.updated` | brain | path, summary |

`display` (optional on any event): `{importance: 0–3, bubble?: str, sfx?: str, spotlight?: bool}` — hints only, never state.

## 10.3 Commands (client → labd)

`research_request {text, attachments[]}` · `approve {approval_id, note?}` · `reject {approval_id, note?}` · `redirect {project, text}` · `feedback {target, value, note?}` · `kill_job {job_id}` · `let_run {job_id}` · `rerun {job_id, force?}` · `pause_lab` / `resume_lab` · `policy_set {key, value}` · `note_save {path, content}` · `ask {text, project?}` · `agent_retire {agent}` · `agent_refine {agent}` · `voice {audio_ref}` — each validated by schema + role (§5.4.4).

## 10.4 SQLite schemas

**`var/lab.db`** (labd is the only writer):
```sql
CREATE TABLE events (
  seq INTEGER PRIMARY KEY, ts TEXT NOT NULL, kind TEXT NOT NULL, v INTEGER NOT NULL DEFAULT 1,
  project TEXT, actor TEXT NOT NULL, corr TEXT, causation INTEGER, payload TEXT NOT NULL, display TEXT);
CREATE INDEX ev_kind ON events(kind);
CREATE INDEX ev_project ON events(project, seq);
CREATE INDEX ev_corr ON events(corr);
CREATE TABLE snapshots (name TEXT PRIMARY KEY, seq INTEGER NOT NULL, payload TEXT NOT NULL);
CREATE TABLE jobs (
  job_id TEXT PRIMARY KEY, project TEXT, kind TEXT NOT NULL, kit TEXT, spec TEXT NOT NULL,
  config_hash TEXT NOT NULL, target TEXT NOT NULL, slot TEXT, priority INTEGER NOT NULL,
  status TEXT NOT NULL, submitted_ts TEXT, started_ts TEXT, ended_ts TEXT,
  final TEXT, error_sig TEXT, wall_s REAL, gpu_s REAL, source TEXT);   -- source: live|library_sweep|bug_gym|diagnostic
CREATE INDEX jobs_hash ON jobs(config_hash, status);
CREATE TABLE metrics (job_id TEXT, key TEXT, step INTEGER, value REAL, PRIMARY KEY(job_id, key, step)) WITHOUT ROWID;
CREATE TABLE artifacts (job_id TEXT, name TEXT, path TEXT, mime TEXT, bytes INTEGER, ts TEXT, PRIMARY KEY(job_id, name));
CREATE TABLE kv (key TEXT PRIMARY KEY, value TEXT);
```

**`var/brain.db`** (brain is the only writer; fully rebuildable except caches):
```sql
CREATE TABLE agent_specs (id TEXT PRIMARY KEY, spec TEXT NOT NULL, updated_seq INTEGER);
CREATE TABLE embeddings (id TEXT PRIMARY KEY, kind TEXT, ref TEXT, text TEXT, vec BLOB);   -- float32[384]
CREATE TABLE paper_chunks (paper_id TEXT, chunk_id TEXT, section TEXT, text TEXT, PRIMARY KEY(paper_id, chunk_id));
CREATE TABLE lessons (id TEXT PRIMARY KEY, text TEXT, kind TEXT, evidence TEXT, created_seq INTEGER);
CREATE TABLE fixes (signature TEXT PRIMARY KEY, class TEXT, fix TEXT, success INTEGER, failure INTEGER, source_job TEXT);
CREATE TABLE budget (day TEXT, provider TEXT, tokens INTEGER, requests INTEGER, PRIMARY KEY(day, provider));
CREATE TABLE labml_models (name TEXT, version INTEGER, path TEXT, n_train INTEGER, metrics TEXT, ts TEXT, PRIMARY KEY(name, version));
```
**`var/llm_cache.db`**: `cache(key TEXT PRIMARY KEY, model TEXT, request TEXT, response TEXT, usage TEXT, ts TEXT, fixture INTEGER)`.

## 10.5 `JobSpec` and the worker line protocol

```python
class JobSpec(BaseModel):
    project: str | None
    kind: Literal["kit", "script", "analysis"]
    kit: str | None                 # "grokking" | "distill" | "nerf" | "materials" | "arena" | "smoke"
    kit_version: str | None
    script: str | None              # path inside var/workspaces/<project>/ (kind=script)
    config: dict                    # validated by the kit's own pydantic model
    seed: int = 0
    priority: Literal["interactive", "project", "whatif", "background"] = "project"
    target: Literal["auto", "local", "kaggle", "colab"] = "auto"
    device: Literal["auto", "cuda", "cpu"] = "auto"
    budget: dict                    # {max_seconds: 120, max_steps?: 30000}
    emit: dict = {"metric_every_steps": 50, "telemetry_every_steps": 250}
    force: bool = False             # bypass dedup
    source: Literal["live", "library_sweep", "bug_gym", "diagnostic"] = "live"
```

Worker stdout lines (one JSON object per line):

| `t` | Fields | Notes |
|---|---|---|
| `ready` | worker, pid, torch, device | once per process |
| `started` | job_id, ts | |
| `metric` | job_id, step, wall, m{key: number} | target metric keys declared by the kit spec |
| `telemetry` | job_id, step, m{…} | mechanistic signals for Oracle/Analysts |
| `artifact` | job_id, name, path, mime | path must be inside the run dir |
| `log` | job_id, lvl, msg | |
| `done` | job_id, status (completed/stopped), final{…} | exactly once per job |
| `error` | job_id, etype, msg, tb | then the worker stays alive (in-process kits) |

stdin control lines: `{"t":"job",…}`, `{"t":"stop","job_id","reason"}`, `{"t":"ping"}`.

## 10.6 Runtime file layout (`var/`)

```
var/
├── lab.db  lab.db-wal  brain.db  llm_cache.db
├── runs/<job_id>/        spec.json  stdout.jsonl  stderr.log  ckpt/  artifacts/  analysis/
├── workspaces/<project>/ code/  venv/ (only when a project needs extra deps)  runs/
├── notes/<project>/      plan.md log.md results.md comparison.md lessons.md  + researcher notes
├── papers/<paper_id>/    paper.pdf  paper.md  pack.json
├── labml/<model>/        <version>.pkl|.pt  meta.json
├── reports/              labml.json  repro_<paper>.json  figures/*.png
├── sessions/             recorded demo sessions for REPLAY
├── backups/  logs/  wandb/  models/fastembed/
```

---
