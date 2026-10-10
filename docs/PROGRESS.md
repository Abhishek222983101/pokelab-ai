# PokéLab — PROGRESS

> One line per sub-phase. Status: ⬜ todo · 🟡 in progress · ✅ done · ❌ blocked. Add the key number when done (e.g. `✅ 62 s to 95% test acc`).
> Rule (Part 13.0.5): update this file and commit after every sub-phase.


## P0

- ✅ **P0.1** Repo & workspace skeleton · ★ · 🔵 — repo tree + README + justfile created
- ⬜ **P0.2** Python env · ★ · 🔵 · 🌐 — 
- ⬜ **P0.3** Node & web fork · ★ · 🔵 — 
- ✅ **P0.4** Secrets & config · ★ · 🔵 · 🔑 — secrets generated into .env, config/*.toml written
- 🟡 **P0.5** Fetch everything (offline-first) · ★★ · 🔵 · 🌐 — datasets/papers/sprites already on disk; fetch_*.sh scripts not written yet
- ⬜ **P0.6** Contracts skeleton · ★★ · 🔵 — 

## P1

- ✅ **P1.1** Store + writer thread · ★★★ · 🔵 — SQLite WAL, single writer thread, append/since/snapshot — 5/5 cargo tests pass
- 🟡 **P1.2** Hub & WebSocket gateway · ★★★ · 🔵 — /api/health + /api/events/since live, e2e-tested; WS hub + static serving pending
- ⬜ **P1.3** Metrics pipeline · ★★★ · 🔵 — 
- ⬜ **P1.4** Job engine & warm pool · ★★★★ · 🟣 — 
- ⬜ **P1.5** Telemetry & power guard · ★★ · 🔵 — 
- ⬜ **P1.6** Auth & pairing · ★★ · 🔵 — 
- ⬜ **P1.7** Supervisor, CLI, replay, doctor · ★★★ · 🔵 — 

## P2

- ⬜ **P2.1** Worker runtime · ★★ · 🔵 — 
- ⬜ **P2.2** Kit interface + `smoke` kit · ★★ · 🔵 — 
- ⬜ **P2.3** Grokking kit — models & data · ★★★ · 🔵 · 🔥 — 
- ⬜ **P2.4** Grokking telemetry hooks · ★★★ · 🔵 · 🔥 🧠 — 
- ⬜ **P2.5** Kit benchmark & pool sizing · ★★ · 🔵 · 🔥 — 
- ⬜ **P2.6** W&B offline logging · ★ · 🔵 · 🔑 — 

## P3

- ⬜ **P3.1** Measure the gateway · ★ · 🔵 · 🔑 — 
- ⬜ **P3.2** Bus client & state projection · ★★★ · 🔵 — 
- ⬜ **P3.3** LLM router · ★★★★ · 🟣 · 🔑 — 
- ⬜ **P3.4** JSON I/O & repair · ★★ · 🔵 — 
- ⬜ **P3.5** Brain main & supervision · ★★ · 🔵 — 

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
