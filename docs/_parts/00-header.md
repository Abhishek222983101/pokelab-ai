# POKéLAB — SYSTEM ARCHITECTURE & BUILD BLUEPRINT

> **Document:** `docs/SYSTEM-ARCHITECTURE.md` · **Version** 1.0 · **Date** 2026-10-10
> **Event** Elevate 1.0 (DJSCE, Mumbai, 10–11 Oct 2026) · **Problem statement** PS03 — *An Evolving AI Research Environment* (portal code likely **EL02**, confirm in the team dashboard)
> **Builder** Abhishek (solo) + Claude (Opus 5.5 wrote this blueprint; Sonnet 5 builds from it)
> **Project root** `~/elevate-ps03/` (this folder) · **Working name** **PokéLab** — *Professor Oak's Evolving Research Lab*
> **Status** Design frozen for P0. Every later decision must cite or amend a section of this document.

---

## HOW TO READ THIS DOCUMENT

| If you are… | Read | Skip |
|---|---|---|
| **The human building and presenting it** | `docs/OVERVIEW.md` first (plain-language tour, ~30 min). Then Part 1 (what the PS demands), Part 2 (the experience), Part 12 (demo + acceptance tests). | Field-level contracts in Part 10 |
| **The AI agent writing the code** | **Everything relevant to your sub-phase.** Part 13 (the build plan) is your work order; each sub-phase names the sections it depends on. Parts 5–10 are the specs. Never "re-design" what a section already decides — cite it (`per §6.4`). | Nothing your sub-phase cites |
| **A reviewer agent checking the code** | Part 1.4 (demand matrix), Part 10 (contracts), Part 11 (non-functional rules), Part 12.3 (acceptance tests AC-1…AC-25) | — |

**Conventions used throughout:**

| Marker | Meaning |
|---|---|
| `[PS-Dn]` | Traces to demand *Dn* of the problem statement (§1.3). Not negotiable. |
| `[DECISION]` | A design decision. Rationale is always given. Can be revisited only with a reason written into §14.2. |
| `[MEASURED]` | A number we produced on *this* laptop or *this* gateway. Only these numbers may go on slides. |
| `[TARGET]` | A number we are aiming for. Never shown to judges as a result. |
| `[RESEARCH]` | Grounded in a cited paper/repo (links in §14.6). |
| `[RISK]` | A known failure mode with a stated mitigation (full register §14.1). |
| `[STRETCH]` | Build only after every non-stretch item of its phase is green. |
| `⚠️` | A verified gotcha — the obvious approach breaks here. |
| 🔥 | Sub-phase needs the GPU at full power: **plug in the charger, set Performance mode, fans on.** |
| 🧠 | Sub-phase is ML-heavy (training, evaluation, model math). |
| 🔑 | Sub-phase needs an API key / account (listed in §13.0.4). |
| 🌐 | Sub-phase needs a good network (downloads). Do it on the phone hotspot if the campus Wi-Fi blocks it. |
| 🟣 Opus / 🔵 Sonnet | Which Claude model should run that sub-phase (Part 13.0.3). Default is 🔵 Sonnet. |
| ★☆☆☆☆ … ★★★★★ | Difficulty of a phase / sub-phase. |

**The three rules this document enforces:**

1. **Real or nothing (the binding rule).** Every sprite movement, speech bubble, HP bar, evolution, number and chart on screen is driven by an event that a real component emitted. The game is a *lens* onto the lab, never a costume. If the backend is idle, the game shows idleness (agents sleep). `[PS-D26]`
2. **Never buffer.** No interaction may leave the screen frozen. Anything slower than 150 ms streams progress; anything slower than 2 s shows *real* intermediate state (agent thoughts, live curves, forecasts). A judge must always see something true moving.
3. **Every claim is measured.** Reproduction numbers, Oracle accuracy, compute saved, BO efficiency — all come from `var/reports/*.json` produced by our own runs (`make eval`). The UI reads those files; it never hard-codes a metric.

---

## DOCUMENT MAP

| Part | Title | Answers |
|---|---|---|
| 1 | The problem statement | What exactly did they ask for? (verbatim + gist + 27 numbered demands + traceability) |
| 2 | The product & the experience | What is PokéLab, how does it feel, how does the Pokémon world map onto the PS? |
| 3 | System architecture | What are the boxes and wires? Processes, data flow, sequence diagrams |
| 4 | Technology stack & repository | Which languages/frameworks/versions, why, and where every file lives |
| 5 | `labd` — the Rust lab core | Event store, gateway, job supervisor, metrics pipeline, telemetry, auth |
| 6 | `brain` — Professor Oak & the agents | Meta-controller, agent runtime, action protocol, LLM router, papers, memory, lifecycle, reward |
| 7 | The ML layer — Oak's Instruments | Oracle, Navigator, Selector, Medic, Scout, Compute Router, Analysts — real ML that makes the lab faster |
| 8 | Workers, kits & the papers | Warm GPU pool, experiment kits, remote Kaggle/Colab, the paper packs and their what-ifs |
| 9 | The game & the console | Phaser scenes, the Director, sprites, audio, React console, mobile Pokégear |
| 10 | Contracts, data model & APIs | Event catalogue, SQLite schemas, WebSocket/HTTP/worker protocols |
| 11 | Non-functional design | Performance budgets, reliability, network plan, security, observability, testing |
| 12 | Demo & acceptance | Storyboard, wow moments, acceptance tests AC-1…AC-25 |
| 13 | **The build plan** | Phases → sub-phases → exact technical steps → done-when gates, difficulty, GPU/ML/API flags |
| 14 | Risks, decisions, references | Risk register, decision log, open questions, glossary, every link and local path |

---
