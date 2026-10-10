# PART 6 — `brain`: PROFESSOR OAK & THE AGENTS

The brain is one Python asyncio process. It holds the lab's *intelligence*: what to do, who does it, how well it went, what was learned. It owns no durable truth — it **publishes events to labd** and **rebuilds its state from the event log** on start (§6.12).

## 6.1 Module map and the main loops

| Loop (asyncio task) | Cadence | Does |
|---|---|---|
| `bus` | continuous | WS to labd: receive events/commands/metrics; publish batches (≤ 20 ms coalescing) |
| `oak.scheduler` | event-driven + 1 Hz tick | advance every running project's plan DAG; dispatch ready steps within concurrency limits |
| `agents.runner` | per task | run an agent's action loop (one task = one asyncio task) |
| `labml.oracle_watch` | 2 s | forecast every running job; early-stop recommendations |
| `labml.trainer` | after each finished job/task | incremental retrain of labml models in a thread pool (< 1 s each) |
| `oak.lifecycle` | after each reward + 30 s tick | evaluate spawn/refine/merge/retire triggers |
| `snapshot` | every 200 events / 15 s | publish `state.snapshot` |
| `llm.budget` | on every call | ledger + `llm.call` events for the HUD |

Concurrency limits (config `lab.toml [brain]`): `max_parallel_tasks = 4`, `max_parallel_llm = 2` (Elevate) + `2` (Groq), `max_steps_per_task = 6`.

## 6.2 Professor Oak — the meta-controller

### 6.2.1 Intake → `ProjectSpec` `[PS-D2]`

Inputs arrive as `cmd.research_request {text, attachments[]}` where attachments are `paper` (PDF path/arXiv id/URL), `dataset` (CSV/Parquet path), `repo` (local path or Git URL), `idea` (free text). One **fast-class** LLM call converts them to:

```python
class ProjectSpec(BaseModel):
    title: str
    kind: Literal["reproduce", "whatif", "compare", "explore", "discover"]
    goal: str                        # one sentence
    papers: list[str]                # paper ids (ingested first, §6.6)
    questions: list[str]             # explicit what-ifs ("what if weight decay = 0?")
    datasets: list[str]; repos: list[str]
    constraints: dict                # e.g. {"max_gpu_minutes": 10, "no_remote": false}
    autonomy: Literal["ask_all", "default", "autopilot"] = "default"
```
Template-matched requests (the demo papers) skip the LLM: `kind` and `papers` are recognised by rule; the LLM only fills `questions`.

### 6.2.2 Capability analysis `[PS-D5]`

Output (event `oak.capability_analysis`):
```json
{"required": [
  {"cap":"paper_read","why":"claims and hyper-parameters live in §3 and App. A","weight":1.0},
  {"cap":"implement","why":"no verified kit config for p=97 2-layer variant","weight":0.8},
  {"cap":"run_experiment","why":"…","weight":1.0},
  {"cap":"repro_compare","why":"PS requires explaining differences","weight":1.0},
  {"cap":"materials_featurize","why":"composition → descriptor vectors","weight":0.9,"new":true}],
 "coverage": {"paper_read":0.91,"implement":0.84,"materials_featurize":0.41},
 "gaps": ["materials_featurize"]}
```
- The LLM (deep class) is constrained to the taxonomy (§6.4.1) but may propose **new** capabilities with a description (→ embedded, compared against all agents by the Scout, §7.5).
- Coverage is computed by the Scout (embeddings × Selector posterior means) — **not** by the LLM.

### 6.2.3 Planning — templates + LLM adaptation

Plans are DAGs of steps. A step:
```python
class PlanStep(BaseModel):
    id: str                      # "s3"
    cap: str                     # capability tag
    title: str                   # "Extract the reproduction spec"
    inputs: list[str]            # artifact refs: "paper:2201.02177", "s2.spec"
    outputs: list[str]           # declared artifact names
    accept: list[Check]          # objective checks (file exists, schema valid, metric present, job completed …)
    budget: Budget               # max_steps, max_tokens, max_gpu_s
    after: list[str]             # dependency ids
    parallel_group: str | None   # what-if fan-out
```
Templates (`brain/pokelab_brain/oak/templates/*.yaml`):

| Template | Steps (simplified) |
|---|---|
| `reproduce` | ingest → read & extract claims/spec → resolve ambiguities (memory + defaults with flags) → configure/implement → env check → smoke run (≤ 20 s) → full run → analyse → compare → report |
| `whatif` | parse question → Navigator space proposal → batch design → runs (parallel, Oracle-pruned) → analyse sensitivity → explain → report |
| `compare` | align conditions (same budget/data/seeds) → run A & B in parallel → statistical comparison → verdict |
| `explore` | Navigator-driven loop until the uncertainty target or budget is met |
| `discover` | Scout searches arXiv → ranks → ingests top-k → summaries in the Library |

The LLM receives the template + ProjectSpec + memory context and may **add, remove or specialise** steps (e.g. add `materials_featurize` for Roost). The result is validated (acyclic, every `cap` known or proposed, every step has ≥ 1 `accept` check, budgets within project constraints) before `project.plan_proposed`.

### 6.2.4 Scheduler

```
on tick / on event:
  for project in running_projects:
     for step in project.ready_steps():            # deps done, not started
        if capacity_available(step.cap):
            agent = selector.choose(step.cap, context(step))   # §7.3 — emits oak.selection
            if agent is None: lifecycle.request_spawn(step) ; continue
            start_task(agent, step)                  # agent.task_assigned → runner
  on task done:  verify(step.accept) → reward → selector.update → maybe unlock next steps
  on task fail:  retry ≤ 2 (re-selection allowed: the next draw may pick another agent)
                 → else escalate: Medic/Debugger, or ask the human (approval card)
```

### 6.2.5 The experiment loop (inside `run`/`whatif` steps) `[PS-D11, D14, D19]`

1. Experimenter agent writes a `JobSpec` (kit + config) — validated by the kit's Pydantic config model.
2. Compute Router picks the target (§7.7); dedup check (§5.5.2).
3. Job runs; Oracle forecasts; early stop if hopeless (policy).
4. For `whatif`/`explore`: after each completed or killed job, the Navigator updates its posterior and proposes the next batch (size 2–3, parallel) until: posterior boundary uncertainty < τ, run budget exhausted, or the human stops it.
5. Results → Analyst kit → Comparator.

### 6.2.6 Comparison projects `[PS-D12]`

Fair-comparison contract enforced by the planner: identical data split + seeds {0,1,2} + equal wall-clock or step budget + same device class. Output: mean ± 95 % CI per approach, paired test across seeds, a verdict sentence generated from the numbers.

### 6.2.7 Autonomy policy and approvals `[PS-D20]`

`config/lab.toml [policy]` (also editable live in the console → `cmd.policy_set` event):

| Action | `default` policy | Approval UI |
|---|---|---|
| Plan | auto-approve; shown on the quest board | — |
| Spawn agent | **ask** (timeout 120 s → reject) | Poké Ball card (desk + phone) |
| Remote job (Kaggle/Colab) | ask if predicted > 2 min | Boat/cable-car card |
| Early stop by Oracle | auto (with 5 s "let it run" veto) | toast with veto button |
| Refine (evolve) | auto if shadow eval passes | notification |
| Merge | **ask** | Day Care card |
| Retire | auto with 10 s veto | faint toast with veto |
| Install a package | auto if on allowlist, else ask | — |

Approvals are events (`human.approval_requested/approved/rejected/expired`); the requesting coroutine `await`s an `asyncio.Future` resolved by the matching human event.

### 6.2.8 Redirect

`cmd.redirect {project, text}` → the planner gets (current plan, finished steps, new instruction) → returns a revised plan (finished steps are immutable) → `project.plan_revised {diff}` → scheduler continues. Running jobs that the new plan no longer needs are stopped with reason `redirect`.

## 6.3 The agent runtime

### 6.3.1 The loop

```python
async def run_task(agent: AgentSpec, step: PlanStep, ctx: Context) -> TaskResult:
    history: list[Turn] = []
    for i in range(step.budget.max_steps):
        prompt = render(agent, step, ctx.pack(step), history, tools_for(agent))   # §6.3.4
        reply = await llm.complete(route=agent.model_route, messages=prompt,
                                   max_out=agent.max_out, agent_id=agent.id)       # §6.5
        turn = protocol.parse(reply)                                                 # §6.3.2–3
        emit("agent.thought", text=turn.thought[:140])
        if turn.final: return verify_and_finish(turn.final, step)                     # §6.3.5
        result = await tools.execute(turn.action, agent, step)                        # §6.4.3
        emit("agent.action_result", ok=result.ok, summary=result.summary[:200])
        history.append(Turn(turn, observe(result)))
    return TaskResult(status="budget_exhausted")
```

### 6.3.2 The action protocol `[DECISION D-06]`

⚠️ `[MEASURED 10 Oct]` The Elevate gateway **does not return `tool_calls`** (Luna/GPT-5-mini burned all 600 output tokens reasoning and stopped; DeepSeek ignored the tools) and **does not enforce `response_format`**. Groq supports native tools, but one protocol everywhere is simpler and testable. Every agent reply must be:

```
<thought>Short reasoning, ≤ 60 words, written for the researcher to read.</thought>
<action>{"tool": "paper.read_section", "args": {"paper": "2301.05217", "section": "3"}}</action>
```
or, to finish:
```
<thought>…</thought>
<final>{"status": "success", "summary": "…", "outputs": {"spec": {…}}}</final>
```

System-prompt tail appended to every agent (exact text in `agents/prompts/_protocol.md`): the tool list (name, one-line purpose, JSON-schema of args), two worked examples, and the rule "exactly one `<action>` or one `<final>` per reply; JSON must be valid; no prose outside the tags".

### 6.3.3 Parsing & repair (`agents/protocol.py`)

1. Extract the first `<thought>`, then `<action>`/`<final>` (regex, DOTALL, tolerant of code fences and whitespace).
2. `json.loads`; on failure `json_repair.loads`; on failure → **one** repair turn: the model gets `FORMAT_ERROR: <error>. Reply again with exactly one <action> or <final>.` (same route, low `max_out`).
3. Validate args with the tool's Pydantic model; validation errors are returned as an observation (the agent fixes its own call).
4. Every format failure is counted in the agent's stats → part of its reward (quality) and a GEPA-lite refinement signal (§6.8.3). Agents literally evolve to follow the protocol better.

Unit tests: 40 recorded real replies (good and malformed) + Hypothesis fuzzing of the tag extractor.

### 6.3.4 Context packs (token discipline)

Each prompt ≤ **6 k tokens** (hard cap 10 k; gateway request cap 48 KB `[MEASURED limit]`):

| Block | Budget | Source |
|---|---|---|
| Agent system prompt (role + protocol + tool docs) | ≤ 1.5 k | spec |
| Task brief (step title, inputs, accept checks, budget) | ≤ 0.4 k | plan |
| Relevant memory (top-k lessons/fixes, nearest past tasks of this capability) | ≤ 1.0 k | §6.7 retrieval |
| Paper excerpts (top-k chunks by embedding for the step) | ≤ 1.5 k | §6.6 |
| History (last 3 turns verbatim; older turns as one-line action records) | ≤ 1.2 k | runtime |
| Observation of the last tool call (head 60 % / tail 40 % truncation) | ≤ 0.8 k | tool |

### 6.3.5 Verifiers (objective first)

Every `PlanStep.accept` check is executed by code, never by the LLM: `file_exists`, `json_schema_valid`, `config_validates(kit)`, `job_completed`, `metric_present(key)`, `metric_threshold(key, op, value)`, `report_has_sections([...])`, `numbers_match_evidence` (claim-guard for reports, §6.10.4). The verifier output feeds the reward's quality term (§6.9).

## 6.4 Agents as data

### 6.4.1 Capability taxonomy (base set; extensible at runtime)

`paper_read` · `spec_extract` · `claim_extract` · `implement` · `code_edit` · `env_setup` · `dependency_fix` · `data_prep` · `debug` · `repair` · `experiment_design` · `whatif_design` · `run_experiment` · `compute_ops` · `remote_run` · `analyze` · `repro_compare` · `explain` · `report_write` · `notes` · `author_email` · `literature_search` · `paper_discover` — plus runtime-added specialisations (e.g. `materials_featurize`, `nerf_render`, `quantize`), each with a description embedded for the Scout.

### 6.4.2 `AgentSpec`

```python
class AgentSpec(BaseModel):
    id: str                          # "agt_charmander_v2"
    name: str                        # "Charmeleon"
    species: str                     # "charmeleon" (sprite key)
    line: str                        # "charmander"  (evolution line)
    version: int                     # 2
    parents: list[str]               # lineage (1 parent = refine, 2 = merge)
    role: str                        # "implementer"
    capabilities: list[str]
    system_prompt: str               # role prompt (versioned text)
    tools: list[str]                 # allowed tool names
    model_route: Literal["deep","act","fast","extract"]
    max_out: int = 1200
    temperature: float = 0.2
    status: Literal["proposed","active","retired","merged","rejected"]
    created_by: Literal["seed","spawn","refine","merge"]
    created_reason: str
    stats: AgentStats                # n_tasks, successes, format_errors, tokens, gpu_s, reward posterior params
```

### 6.4.3 Tools (each = name, Pydantic args, async `run()`, permission list)

| Tool | Args (abridged) | Effect |
|---|---|---|
| `paper.list_sections` / `paper.read_section` / `paper.search` | paper, section / query, k | text from the ingested paper (§6.6) |
| `memory.search` | query, kinds[lessons,fixes,runs,configs], k | Pokédex retrieval (§6.7) |
| `memory.lookup_config` | kit, config | dedup check & previous results |
| `code.read` / `code.write` / `code.edit` | path, (content) / (start, end, new_text) | inside `var/workspaces/<project>/` only; `edit` = Agent-Lab-style line-range replace |
| `code.list` | dir | — |
| `env.check` / `env.install` | packages[] | `uv pip install` into the project venv; allowlist in `config/lab.toml` |
| `data.inspect` | path | schema, row count, head, class balance (CSV/Parquet/NPZ) |
| `repo.inspect` | path/url | tree, README, entry points (git clone `--depth 1` to workspace) |
| `job.submit` | kit or script, config, budget, priority, target? | via labd (§5.4.3) |
| `job.status` / `job.metrics` | job_id, keys | summaries (last values, best, slope) — never raw floods |
| `job.stop` | job_id, reason | — |
| `analysis.run` | analyst, job_ids | §7.8 analyst kits |
| `compare.run` | project | ReproComparator (§6.10) |
| `notes.write` / `notes.append` | path, markdown | `var/notes/<project>/` |
| `discover.arxiv` | query, k | arXiv API (cached) |
| `human.ask` | question, options | approval/question card (desk + phone); awaits answer or timeout |
| `finish` | — | equivalent to `<final>` |

## 6.5 LLM router `[MEASURED 10 Oct unless noted]`

### 6.5.1 Provider facts

| Provider / model | Latency (observed) | Notes |
|---|---|---|
| Elevate `gpt-5.6-luna` | 0.4 s tiny · **6.9 s** for 2.2 k-in / 674-out (512 reasoning tokens) | Best extraction quality; reasoning tokens count toward the 4 000 output cap → give `max_completion_tokens ≥ 1500` |
| Elevate `deepseek-v4-pro` | **2.0–3.3 s** for 2.2 k-in | Fast, no reasoning-token burn; `max_tokens` param; occasionally terse |
| Elevate `gpt-5-mini` | 6.7 s; burns ~64 reasoning tokens even for "OK" | Last-resort only |
| Groq `qwen/qwen3.8-27b` | **0.9 s** | Native tools work. Limits (Groq docs, free tier) are **per organisation, not per key**: 30 req/min, 1 000 req/day, **8 000 tokens/min**, 200 k tokens/day — the two keys only add capacity if they belong to different organisations |
| Groq `openai/gpt-oss-20b` / `-120b` | 0.8 s / 3.7 s | Same limits; needs a custom `User-Agent` |
| Elevate limits | 800 k tokens/day/team (reset 05:30 IST); **~10 rapid requests → 429 with `Retry-After: 60`**; 6 parallel → 4 rejected | Exact per-minute ceiling re-measured in P3.1 (network was failing at 1.6 s RTT during the first probe) |

### 6.5.2 Routes (`config/llm.toml`)

| Route | Used for | Order (first available wins) |
|---|---|---|
| `extract` | paper claims/spec extraction, plan drafting | `gpt-5.6-luna` → `deepseek-v4-pro` → `groq:gpt-oss-120b` |
| `deep` | comparator narrative, spawn spec drafting, refinement reflection, redirect | `deepseek-v4-pro` → `gpt-5.6-luna` → `groq:gpt-oss-120b` |
| `act` | agent loop steps | `deepseek-v4-pro` → `groq:gpt-oss-120b` → `gpt-5.6-luna` |
| `fast` | intake, classification, bubble summaries, voice-command parsing | `groq:qwen3.8-27b` → `groq:gpt-oss-20b` → `deepseek-v4-pro` |

### 6.5.3 Algorithm

```
complete(route, messages, max_out, agent_id):
    key = sha256(model_family(route) | canonical(messages) | max_out | temperature)
    if cache.hit(key) and (mode != "live" or cacheable(route)): return cached (llm.call{cached:true})
    est_in = chars/3.6 ; est_total = est_in + max_out
    if request_bytes > 46_000: compact(messages)  # drop oldest history, shrink excerpts
    for model in routes[route]:
        p = provider(model)
        if p.circuit_open or not p.bucket.try_take(est_total, 1 request): continue
        try (timeout 45 s, 1 retry on timeout/5xx with jitter):
            resp = await p.call(model, messages, out_param(model)=max_out)
        except 429: p.open_circuit(retry_after or 60); continue
        except 403 quota: p.mark_daily_exhausted(); continue
        record usage (actual tokens) → budget ledger → llm.call event
        cache.put(key, resp); return resp
    raise AllProvidersBusy  → caller backs off (task waits, bubble shows "waiting for a free brain…")
```
- **Groq prompts must be compact**: a full 12 k-token gateway-size prompt cannot fit an 8 k tokens/min budget → the router asks the context packer for a *compact variant* (≤ 5 k input + max_out ≤ 1 k) before sending to Groq.
- Clients: one `openai` 3.28 `AsyncOpenAI` per provider with `max_retries=0` (the router owns retries) and a custom `User-Agent`.
- **Token buckets** per provider: start Elevate at 6 req/min & 60 k tok/min (adaptive: −50 % on 429, +10 % per clean minute); Groq per key 8 000 tok/min, 1 000 req/day (read `x-ratelimit-*` headers to resync).
- **Priority queue** in front of the buckets: human-facing calls (redirect, ask) > plan > agent steps > background summaries.
- **Modes:** `live` (cache read+write), `llm-replay` (cache-only; a miss raises — used for offline rehearsal), `record` (live + mark entries as demo fixtures).
- **Budget ledger:** tokens per provider per day persisted in `brain.db`; HUD shows "Elevate 612k / 800k left · Groq 1.8k req left". Hard stop at 95 % of the daily allowance for non-human calls.

### 6.5.4 Token plan for the demo day `[TARGET]`

| Activity | Calls | ≈ Tokens |
|---|---|---|
| One reproduction project (ingest/extract/plan/configure/analyse/compare/report) | 12–18 | 50–70 k |
| One what-if batch (design + explain) | 3–5 | 12–20 k |
| Lifecycle events (spawn draft, refinement reflection, merge synthesis) | 3–6 | 15–25 k |
| Judge interactions (ask/redirect, voice) | 5–10 | 10–20 k |
| **Full demo (4 papers + what-ifs + lifecycle)** | ~90 | **≈ 300–400 k** of 800 k — paper ingestion/extraction for the 4 demo papers is done and cached before the demo |

## 6.6 Papers & inputs `[PS-D2, D17]`

### 6.6.1 Ingestion

PDF → `pymupdf4llm.to_markdown(…, use_ocr=False)` in a process pool (~0.55 s/page in layout mode `[MEASURED]` → 10–20 s per paper; the demo papers are pre-ingested) → split by headings into sections → chunks ≤ 1 200 tokens with ids (`§3.1#2`) → fastembed vectors → `brain.db`. Figures/tables keep their captions as chunks (claims often live in captions). Ingestion is cached by PDF sha256.

### 6.6.2 `PaperPack` (the machine-readable paper)

```python
class Claim(BaseModel):
    id: str; statement: str; metric: str; value: float | None; unit: str | None
    dataset: str; conditions: dict; location: str          # "Fig. 1 (left)", "Table 2"
    evidence_chunks: list[str]; tolerance: float | None     # how close counts as reproduced
class ReproSpec(BaseModel):
    model: dict; optimizer: dict; data: dict; training: dict; evaluation: dict
    unspecified: list[str]                                  # details the paper does not give (seeds, init…)
class PaperPack(BaseModel):
    paper_id: str; title: str; authors: list[str]; year: int; domain: str
    claims: list[Claim]; spec: ReproSpec; whatif_suggestions: list[str]; known_pitfalls: list[str]
```
Extraction = one `extract` call per section group, merged and validated; every field cites chunk ids; the console **Library** highlights cited spans. For the four demo papers, packs are generated in P4/P11 by the lab itself and **human-reviewed** (corrections are saved as `paper.pack_corrected` events — the system learns from corrections too). `[RESEARCH]` known paper errata (e.g. Nanda's inconsistent weight-decay timings) are stored as `known_pitfalls`.

### 6.6.3 Discovery

`discover.arxiv` (`arxiv` 4.0.1: `Client(delay_seconds=3).results(Search(…))`, ≤ 1 request / 3 s, PDFs fetched from `pdf_url`) → Scout ranks by embedding similarity to the project goal + recency → top-k summaries in the Library; ingestion on demand. Cached for offline use.

### 6.6.4 Datasets & codebases as inputs

- **Dataset** (CSV/Parquet/NPZ): `data.inspect` profiles it → the planner picks a kit able to consume it (e.g. the `arena` kit for tabular data: tree vs MLP comparison per Grinsztajn) → experiments.
- **Codebase** (local path or Git URL): `repo.inspect` → entry point + requirements → Env Engineer builds a `uv` env in the workspace → script job with the JSON-lines shim (`workers/script_runner.py` wraps stdout and converts `print`-style metrics via regex templates the agent proposes).
- **Idea / question** without a paper: `explore` template with the Navigator.

## 6.7 Memory — the Pokédex `[PS-D15, D16]`

| Store | Content | Key / retrieval | Writer |
|---|---|---|---|
| Event log | everything | seq/kind/project | labd |
| Config index | completed jobs by `config_hash` | exact hash | labd (`jobs` table) |
| Lessons | short verified statements ("wd=0 never grokked in 30k steps at frac 0.3 — runs job_…") | embedding kNN + kind filter | brain (`memory.lesson_saved`) |
| Fix library | error signature → fix (patch/config/env) + success count + source run | exact signature, then embedding kNN (Medic §7.4) | brain |
| Agent history | per-agent task outcomes & traces | agent id, capability | derived from events |
| Paper chunks | ingested papers | embedding kNN | brain |
| Curve library | full metric histories of every run | job id, kit | labd `metrics` table (Oracle training data §7.1) |

**Rule:** a lesson is saved only with a link to the run(s) that support it — memory never stores an unsupported claim (`[RESEARCH]` AgentRxiv documented hallucinated results in shared memory; we close that hole).

## 6.8 Lifecycle — spawn, refine, merge, retire `[PS-D7, D9, D10]`

### 6.8.1 Triggers (evaluated after every reward and every 30 s)

| Action | Trigger (defaults in `lab.toml`) |
|---|---|
| **Spawn** | Scout coverage of a required capability < 0.55, **or** a failure cluster (≥ 3 failures of the same class with no agent whose posterior mean on it > 0.5) |
| **Refine** | agent with ≥ 4 tasks and (recent failure rate ≥ 40 % **or** format-error rate ≥ 20 %) with a recurring Medic class |
| **Merge** | two active agents with capability Jaccard ≥ 0.6, spec-embedding cosine ≥ 0.85, and both under 25 % of their capability's assignments in the last 20 tasks |
| **Retire** | ≥ 5 tasks and P(mean reward < 0.35) ≥ 0.9 under its Beta posterior, **or** dominated: another agent with P(μ_other > μ_this) ≥ 0.95 for all its capabilities |

### 6.8.2 Spawn

Spec drafting (deep route), ADAS-style `[RESEARCH]`: the prompt includes the gap description, the nearest 3 agents (as "stepping stones") and the archive of past spawns with their outcomes; output = `AgentSpec` JSON (validated). Species = Eevee (§2.4). Prior = the nearest agent's posterior on related capabilities, variance inflated ×3 (Selector §7.3.3). Approval per policy.

### 6.8.3 Refine — GEPA-lite `[RESEARCH]` (Agrawal et al., GEPA, ICLR 2026)

1. Collect the agent's last ≤ 8 traces with rewards, verifier results and Medic classes.
2. Reflection call (deep route): "Here is your prompt and these failed/succeeded traces; diagnose and rewrite your system prompt; keep what worked." → candidate v(n+1).
3. **Shadow evaluation:** replay ≤ 4 recorded tasks of that capability against v(n+1) with the LLM cache disabled for the new prompt only (tool results replayed from the event log where deterministic; jobs reused via dedup, so no GPU cost) → per-task reward vector.
4. Promote only if mean reward improves by ≥ 0.05 **and** no task regresses by > 0.1 (Pareto-style acceptance). Else `agent.refine_rejected` (the attempt is still in the lineage as a dead branch — honest evolution).
5. Promoted → `agent.evolved {from, to, delta, evidence}` → species evolves to the next stage of its line; posterior restarts from the parent's mean with inflated variance.

### 6.8.4 Merge

Synthesis call: union of capabilities, merged prompt keeping both agents' best-scoring instructions → shadow-evaluate on both parents' recent tasks → accept if ≥ max(parent means) − 0.03 → `agent.merged {parents, child}`; parents status `merged`. Species = the higher-reward parent's line, shown hatching from an egg at the Day Care.

### 6.8.5 Retire

`agent.retired {reason, posterior, last_tasks}`; the agent's tasks are re-assigned; its history stays in Bill's PC (and is still used as data by the Scout and Selector priors).

## 6.9 The reward engine `[PS-D8]`

For a finished task:

```
S = 1 if verifier passed all accept checks else 0
Q = capability-specific quality in [0,1] (table below)
T = 1 - min(1, latency / latency_budget(cap))          # timeliness, counts only on success
C = min(1, tokens / token_budget(cap)) * 0.5 + min(1, gpu_s / gpu_budget(cap)) * 0.5
r_base = 0.40*Q + 0.20*S + 0.20*S*T + 0.20*(1 - C)
if human feedback H present (👍=1, 👎=0, or stars→[0,1]):  r = 0.5*r_base + 0.5*H
else r = r_base
```
- A fast failure scores ≤ 0.2 (Q≈0, S=0) — so agents that fail cheaply are still retirable (the bug in the earlier draft formula is fixed).
- **Quality Q by capability:** `spec_extract` = fraction of spec fields that match the human-reviewed pack (when available) else schema completeness × citation rate; `implement` = smoke run passes (1) / runs but metric missing (0.5) / crashes (0); `run_experiment` = 1 − min(1, |ours − claim| / tolerance) for reproduction steps, or "informative" (completed or early-stopped with Oracle confidence) for what-ifs; `debug` = rerun succeeds after the fix; `repro_compare` = claim-guard passes × fraction of causes with evidence; `report_write` = required sections present × claim-guard; LLM-as-judge only for `explain`, weight capped at 0.3 of Q and flagged in the breakdown.
- **Project-level credit:** when a project ends, each participating agent gets a bonus reward (0.1 × outcome) scaled by its step's criticality (on the critical path = 1, otherwise 0.5).
- Every reward is published as `agent.rewarded {Q,S,T,C,H,r,breakdown}` — the XP-bar tooltip shows it.

## 6.10 ReproComparator — "where and why do we differ?" `[PS-D13, D24]`

### 6.10.1 Quantitative verdict
Per claim: our value (mean ± CI over seeds) vs the paper's value with tolerance → `REPRODUCED` (within tolerance), `QUALITATIVE` (shape/direction matches, numbers outside tolerance), `NOT_REPRODUCED`.

### 6.10.2 Difference hypotheses
Candidate causes come from (a) the **paper's checklist** (`science/checklists/<paper>.yaml`, e.g. the 17-item grokking list: optimizer regime, AdamW vs Adam+L2, steps vs epochs, budget truncation, seed variance, data fraction sensitivity, dataset definition, precision/softmax collapse, Adam ε, architecture/tokenisation, init scale, weight-decay scope, LR/warm-up, metric threshold definitions, regularisers, paper errata, hardware/determinism), (b) the **config diff** between our run and `PaperPack.spec` (including every `unspecified` field we had to assume), (c) **measured sensitivities** from our own what-if runs (Navigator data).

### 6.10.3 Diagnostic runs (the system tests its own explanations)
For the top 1–3 hypotheses that are cheap to test (Router estimate < 60 s), the comparator schedules **diagnostic jobs** (e.g. "rerun with 3 more seeds", "use the paper's β2", "switch Adam+L2 ↔ AdamW") and updates each hypothesis' evidence score from the outcome. This turns "why do results differ?" from speculation into an experiment `[PS-D13]`.

### 6.10.4 Report + claim guard
The narrative (deep route) is generated **only from the evidence table**; a regex claim-guard verifies that every number in the text appears in the evidence table (± rounding); violations → regenerate once → else template text. Output: `var/notes/<project>/comparison.md` + `report.comparison_ready` event + console panel with 👍/👎 (feeds the reward of the agents involved).

## 6.11 Notes, documents, collaboration `[PS-D17]`

- `var/notes/<project>/`: `plan.md` (auto, revisions appended), `log.md` (Scribe summaries of milestones), `results.md`, `comparison.md`, `lessons.md`, plus free researcher notes. Editable in the console (textarea + live preview); saves are events.
- **Exports:** project bundle (`.zip`: notes + figures + `runs.csv` + configs) and print-to-PDF stylesheet.
- **Collaborators:** a `view`-role link/QR (§5.8) shows reports, notes, curves read-only.
- **Authors:** `author_email` capability (Scribe) drafts a polite email to the paper's corresponding author summarising the reproduction and the open discrepancy — saved as a draft file, never sent automatically.

## 6.12 Crash recovery and snapshots

On start: `GET /api/bootstrap` (internal) → load the latest `state.snapshot` → replay events since → rebuild projects, plans, agent specs & stats, selector posteriors, pending approvals (expired ones get the policy default) → re-attach to running jobs (labd still runs them) → resume scheduler. Running *agent loops* are not resumable mid-step: their tasks are marked `interrupted` and re-dispatched (idempotent tools: writes are content-addressed; job submits dedup by hash). Target **≤ 10 s from crash to resumed** (AC-23).

---
