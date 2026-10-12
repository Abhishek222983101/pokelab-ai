# PokéLab — Prof. Oak's Evolving Research Lab

An **event-sourced multi-agent ML research lab**, skinned as a Pokémon game. Type *"Reproduce grokking"* and Professor Oak
plans the work, picks agents (Pokémon) by their learned reward record, and they run **real training jobs on a GPU**.
Every move, number and animation on screen is derived from a logged event — nothing is scripted.
Built for **Elevate 1.0, PS03 "An Evolving AI Research Environment"** (DJSCE, 10–11 Oct 2026).

| | |
|---|---|
| **Live desk** | https://pokelab-ai.vercel.app/lab/ — a static front end; it shows live data only while the author's laptop backend + tunnel are running (see *Hosting* below) |
| Code | https://github.com/Abhishek222983101/pokelab-ai (canonical) · mirror: https://github.com/ELEVATE-1-0/ELEV04 |
| Full project brief (for humans or another AI session) | [`docs/PROJECT-BRIEF.md`](docs/PROJECT-BRIEF.md) |
| Honest gap analysis vs the problem statement | [`docs/GAP-ANALYSIS.md`](docs/GAP-ANALYSIS.md) |
| Architecture blueprint | [`docs/SYSTEM-ARCHITECTURE.md`](docs/SYSTEM-ARCHITECTURE.md) · plain-language tour: [`docs/OVERVIEW.md`](docs/OVERVIEW.md) |

## What it does (verified live)
Five papers reproduce end to end on a laptop GPU, each judged by comparing the *measured* metric to the paper's claim:

| Paper | Measured | Claim |
|---|---|---|
| Grokking (Power / Nanda) | test_acc **0.991** | 0.95 |
| Knowledge distillation (Hinton) | **0.8985** | 0.88 |
| Materials / superconductor Tc (gradient boosting) | R² **0.906** | 0.90 |
| Tree vs MLP on tabular data (Grinsztajn) | **0.8515** | 0.84 |
| Tiny NeRF (Mildenhall) | PSNR **17.9** | 15 |

Plus a real **"What if?"** study: *"What if weight decay is zero?"* runs a 6-cell grid (weight decay × data fraction),
each cell a real grokking run, and the **Safari** tab shows which settings grok.

## How to play (the `/lab/` desk)
1. Click **Reproduce grokking** (or any quick prompt, or type a request) → the **NOW** card shows the running step; agents
   walk to their stations with speech bubbles built from real results.
2. **PAPER** tab: the real paper text the Reader extracted, the claim Oak extracted, and the measured analysis
   (e.g. "train acc 0.99 at step 100, test acc 0.95 at step 1900 — an 1800-step delay").
3. **ACTIVITY**: click any row → **PROOF**: the exact logged event JSON and related events.
4. **EXPERIMENTS**: live curve vs the paper's claim, run table with verification (final = last streamed point).
5. **SAFARI**: click *What if weight decay is zero?* and watch the tiles fill in with real runs.
6. **TEAM**: click an agent → reward record, lineage (evolved / de-evolved), work log; 👍/👎 feeds its reward.
   *De-evolve team* resets the evolution demo. Shift+E overlays event ids on animations.

## How it works
```
browser (Next.js static export: Phaser room + React panels)  ⇄ WebSocket
  labd  (Rust)  — append-only SQLite event log  var/lab.db  — job engine — warm GPU worker pool
  brain (Python) — Professor Oak: plan → Thompson-sampling agent choice → real executors → verdict → rewards
  workers/kits   — grokking · distillation · nerf · materials · arena  (real PyTorch / sklearn training)
```
State everywhere (agent levels, plan status, tiles, paper evidence) is a **fold of events**, so the log replays to
identical state and survives restarts. Agents are deterministic executors with a Pokémon identity (not LLMs);
selection is Beta-Bernoulli **Thompson sampling** over logged rewards; evolution is a stated rule
(≥N rewarded tasks, mean reward ≥0.9). See the brief for the full ML inventory and what is *not* live.

## Status — honest summary
✅ live: 5-paper reproduction, what-if grid, real paper-text evidence, event proof, reward/feedback loop,
rule-based evolve/de-evolve, crash recovery · 🟡 partial: explain-why-it-differs, phone control, spawn/merge/retire
(code + tests, not triggered live) · ❌ not built: cross-run memory/dedup, Kaggle/Colab in the live loop, walkable
Pokémon world (maps & art exist; scenes not connected), arbitrary-paper ingestion.
Details and priorities: [`docs/GAP-ANALYSIS.md`](docs/GAP-ANALYSIS.md), next steps: brief §13.

## Layout
| Dir | What |
|---|---|
| `core/` | Rust: `labd`, event store, job engine, WebSocket gateway, telemetry |
| `brain/` | Python: Oak runtime, scheduler, executors, what-if, agents, LLM router, papers |
| `labml/` | Python: Selector (live), Oracle, Navigator, Medic, Scout, Router, Analysts (built, mostly not wired) |
| `workers/` | Python: GPU worker pool + the five kits |
| `web/` | Next.js/TypeScript: `/lab` desk (room scene + panels), `/m` phone, game assets/maps (PokeStonks fork) |
| `contracts/` | Event/command types shared by Rust, Python and TypeScript |
| `docs/` | brief, gap analysis, architecture, game design, progress log |
| `scripts/` | `live_up.sh`, `deploy_vercel.sh`, chaos drills, asset/data fetchers, acceptance suite |

## Run it locally
```bash
just init       # .env from example + generated secrets, deps          (LLM keys optional)
just fetch      # datasets, paper PDFs, sprites (network once)
just atlases    # build sprite atlases into web/public/assets/gen/ (not committed)
cd web && npm install && npm run build && cd ..
just live       # starts labd + brain (+ cloudflared tunnel) and prints the links
# → open http://localhost:7700/lab/ and click "Reproduce grokking"
just test       # per-project: cargo test, pytest (brain/labml/workers/contracts), vitest
just doctor     # preflight: GPU / disk / assets / datasets / LLM reachability
```
Needs an NVIDIA GPU for the fast grokking/NeRF runs (CPU works, slower). Without LLM keys Oak only accepts requests
that name a known paper. **Never commit `.env`.**

## Hosting
The Vercel site (`just deploy` → `scripts/deploy_vercel.sh`) is static. It connects to a backend through
`NEXT_PUBLIC_BACKEND_HOST` (a Cloudflare quick tunnel to the laptop running `just live`); when the tunnel address
changes, redeploy. Moving labd + brain + a GPU worker to a persistent host removes that dependency.

## Credits
Built on the PokeStonks engine (Phaser 3 + grid-engine), web3 parts stripped. Pokémon sprites and cries come from
public fan asset mirrors (PokeAPI / Showdown / PMDCollective), fetched locally and **not committed**, used for a
non-commercial hackathon demo. Papers: Power et al. 2022, Nanda et al. 2023, Hinton et al. 2015, Mildenhall et al. 2020,
Hamidieh 2018, Grinsztajn et al. 2022.
