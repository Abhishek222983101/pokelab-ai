# PokéLab — The Plain-Language Overview

> For the human. Read this first (≈ 30 minutes). The full technical blueprint is `docs/SYSTEM-ARCHITECTURE.md`; this file explains the *ideas*, the *moving parts*, and *where the important code lives*, so you always understand what the AI is building and why.

---

## 1. What we are building, in one breath

A research lab run by a team of AI agents that you can **watch, play and steer like a Pokémon game**.

You (Ash) give the lab research work — "reproduce this paper", "what happens if I remove weight decay?", "compare these two methods", or just a CSV file. **Professor Oak** (the AI boss, called the *meta-controller* in the problem statement) figures out what skills are needed, picks Pokémon (the AI agents) to do each step, and **creates new specialists when nobody on the team can do something**. The agents read papers, configure and write code, run **real training on the laptop's GPU** (or on Kaggle/Colab), fix failures, and finally explain **where and why our results differ from the paper**.

Everything is scored. Good agents **evolve** (Charmander → Charmeleon) after a *measured* improvement; weak ones **faint** and are retired; redundant ones are **merged** at the Day Care. And underneath, **seven small machine-learning models trained on the lab's own history** make the lab faster and smarter every time it runs something.

## 2. Why a game? (and why it is not a gimmick)

The problem statement says the interface must show *what agents are doing, why, how well, and how the team evolves* — **not a notebook or a chat box**. A Pokémon world does that naturally:

- A Pokémon walking to the **library desk** = an agent reading a paper *right now*.
- A **Gym battle** = a real training run. **Our HP** is the compute budget left; the **Gym Leader's HP** is how far we still are from the paper's number. When grokking suddenly happens, it's "super effective!".
- **Evolution** = a real, measured upgrade of an agent. **Fainting** = retirement. **A wild Eevee appearing** = the lab detected a missing skill and wants to hire a specialist (you approve it from your phone).
- The **Pokédex** = the lab's memory.

The iron rule: **the game only shows what really happened.** Every animation is triggered by an event from the backend. If the lab is idle, the Pokémon sleep. Press `Shift+E` and every animation shows the ID of the event that caused it — proof for the judges.

## 3. The four layers (who does what)

```
   YOU (desk browser + phone)
        │   sees the game + console; sends requests, approvals, redirects
        ▼
 ┌──────────────┐   the "nervous system" — Rust
 │    labd      │   stores every event, streams them to screens, runs & kills training jobs,
 │              │   watches the GPU and the power cable. Never thinks about research.
 └──────┬───────┘
        │
 ┌──────▼───────┐   the "brain" — Python
 │    brain     │   Professor Oak + agents + LLM calls + memory + the 7 ML models.
 │              │   Decides everything. Rebuilds itself from the event log after a crash.
 └──────┬───────┘
        │ asks labd to run jobs
 ┌──────▼───────┐   the "muscles" — Python + PyTorch on the RTX 5050
 │   workers    │   pre-warmed processes that start training in ~10 ms; also send jobs
 │              │   to Kaggle and Colab and stream the results back the same way.
 └──────────────┘
```

**Why three languages?**
- **Rust** for `labd` because it must never stutter or crash while thousands of updates flow to the screens. It's small and stable.
- **Python** for the brain and the training, because all the ML tools (PyTorch, scikit-learn) live there.
- **TypeScript** for the game and console, because it runs in the browser, and we reuse your PokeStonks engine.

They talk with plain JSON. No complicated infrastructure that can break on a demo laptop.

## 4. The life of a research request (what actually happens)

1. You type: *"Reproduce Grokking and test weight decay = 0"* and drop the PDF.
2. **Oak analyses capabilities**: this needs reading, configuring code, running, analysing, comparing. It checks the team: does anyone cover each skill well enough? (The **Scout** model answers that.)
3. **Oak makes a plan** (a small flowchart of steps), from a template that the LLM adapts.
4. For each step, Oak **picks an agent** (the **Selector** model chooses based on each agent's track record) — you see the choice card.
5. The **agent works**: it thinks (its real thought appears in a bubble), uses tools (read a paper section, edit a config, submit a training job), and finishes. An automatic **verifier** checks the result; a **reward** is computed; the agent's track record updates.
6. **Training runs** on a warm GPU worker. The **Oracle** model watches the learning curve and predicts whether it will reach the paper's result; hopeless what-if runs are stopped early ("Got away safely! Saved 41 GPU-seconds").
7. For open questions, the **Navigator** model picks the next most informative experiments and maps the answer (the Safari Zone map slowly un-fogs).
8. If something crashes, the **Medic** model recognises the failure and applies a known fix instantly — or hands it to the Debugger agent with similar past cases.
9. The **ReproComparator** writes the "why our numbers differ" report — and even schedules small diagnostic runs to test its own explanations.
10. Everything learned goes into the **Pokédex** (memory). Run the same config again and the lab answers instantly from memory.

## 5. The ML layer, explained simply (this is what makes it more than "LLM calls")

LLMs are great at **language and code**. They are bad at **numbers, statistics and fast repeated decisions** (they're slow — 2–7 seconds per call on our gateway — expensive, rate-limited, and they don't learn from our own data). So we use seven small, fast ML models exactly where LLMs are weak. Each one *must* prove its value with a measured number.

| Instrument | Plain explanation | Why it matters | How we prove it |
|---|---|---|---|
| **Oracle** | Looks at the first part of a training curve and predicts the end — including grokking *before it happens*, using the same "hidden progress" signals the Nanda paper discovered | Stops doomed runs early → saves GPU time; makes battles exciting ("grokking predicted in ~1,200 steps") | Prediction accuracy vs how much of the curve it has seen; GPU-seconds saved; it gets better as the lab runs more experiments |
| **Navigator** | Decides which "what if" experiment to run next, by modelling what we know and where we're most unsure | Answers questions with far fewer runs than trying everything | Runs needed to map the answer vs a full grid search |
| **Selector** | Picks the best agent for each task by learning each agent's reliability (Thompson sampling) | Better agents get more work; new agents still get a fair try | Total reward vs simple strategies |
| **Medic** | Recognises error messages it has seen before and recalls the fix | Instant repairs without spending LLM tokens | % of failures fixed without the LLM; tokens saved |
| **Scout** | Measures whether the team really covers a needed skill; spots duplicate agents | Drives spawning and merging | Accuracy on a labelled set |
| **Compute Router** | Predicts how long a job will take here vs on Kaggle/Colab | Long jobs go to the cloud, short ones stay local | Prediction error |
| **Analysts** | Look *inside* trained models (e.g. the Fourier "clock" a grokked network learns) | Real science for the "why" | The paper's own measures computed on our models |

Important: **none of them slows the demo.** They load in under a second, answer in milliseconds, and retrain in the background after each run. Their training data is created by the lab itself during the build (hundreds of real runs — the "curve library") and grows during the demo.

## 6. The papers (the four Gyms)

| Town / Gym | Domain (from the PS) | Paper | What we reproduce | The "what if" |
|---|---|---|---|---|
| Modulo City — Sabrina | CPU-scale ML | **Grokking** (Power et al. 2022; Nanda et al. 2023 setup) | Delayed generalisation: training accuracy perfect early, test accuracy jumps much later (~62 s on our GPU) | Weight decay = 0 → no grokking within budget; plus a map over weight decay × data fraction |
| Edge Port — Lt. Surge | Edge & efficient ML | **Knowledge distillation** (Hinton et al. 2015) | A small student trained on a big teacher's soft outputs beats the same student trained alone (MNIST) | Temperature sweep; leave a digit out of the student's data |
| Lumen Town — Blaine | 3D | **Tiny NeRF** (Mildenhall et al. 2020) | A 3D scene learned from photos; new views rendered (PSNR rising live) | Remove positional encoding → blurry/collapsed renders |
| Crystal Cave — Brock | Materials science | **Matbench** (Dunn et al. 2020) baseline + a Roost-style model | Predict material properties from composition; match the published baseline error | Composition-only attention model vs the baseline; data-size learning curve |
| (Arena) — Erika | Comparison | Trees vs neural nets on tabular data (Grinsztajn et al. 2022) | Trees beat MLPs on medium tabular data (measured: electricity 0.880 vs 0.818) | Add noise features (gap widens) · rotate the data (ranking flips — measured) · your own CSV |

All of these run in seconds-to-minutes on this laptop (measured). Datasets are already downloaded.

## 7. Where the important code lives (your map of the codebase)

| If you want to understand… | Look at |
|---|---|
| How events are stored and streamed | `core/crates/lab-store`, `core/crates/lab-gateway` |
| How training jobs start, stream and get killed | `core/crates/lab-jobs`, `workers/pokelab_workers/pool_main.py` |
| How Oak plans and schedules | `brain/pokelab_brain/oak/{planner,scheduler}.py` + `oak/templates/*.yaml` |
| How an agent thinks and acts | `brain/pokelab_brain/agents/{runtime,protocol}.py` + `agents/prompts/*.md` |
| Which LLM is called and why | `brain/pokelab_brain/llm/router.py` + `config/llm.toml` |
| How rewards are computed | `brain/pokelab_brain/reward.py` |
| How agents evolve / merge / retire | `brain/pokelab_brain/oak/lifecycle.py` |
| The ML models | `labml/pokelab_labml/{oracle,navigator,selector,medic,scout,router,analysts}/` |
| The experiments themselves | `workers/pokelab_workers/kits/<paper>/` |
| How "why we differ" is decided | `brain/pokelab_brain/science/comparator.py` + `science/checklists/*.yaml` |
| How events become animations | `web/app/game/director/` |
| The screens | `web/app/game/scenes/` (game), `web/app/console/` (panels), `web/app/m/` (phone) |
| All message formats | `contracts/pokelab_contracts/` (one source; generated for Rust/TS) |

## 8. The build, phase by phase (what each phase delivers)

| Phase | What you'll have at the end | Difficulty | Needs |
|---|---|---|---|
| **P0 Foundations** | Repo, environments, all assets/datasets offline, message formats | ★★ | good network |
| **P1 labd core** | Events stored and streamed live; jobs run and die cleanly | ★★★★ | — |
| **P2 Workers + grokking** | Real grokking runs on the GPU, streaming to the screen | ★★★ | 🔥 plugged in |
| **P3 Brain + LLM router** | Robust LLM access despite rate limits; crash-proof brain | ★★★★ | API keys |
| **P4 Agents & Oak** | **The vertical slice: the lab reproduces grokking by itself** | ★★★★★ | 🔥 + keys |
| **P5 ML layer** | Oracle, Navigator, Selector, Medic, Scout, Router, Analysts — measured | ★★★★★ | 🔥 + W&B key |
| **P6 Lifecycle** | Spawn, evolve, merge, retire — with evidence | ★★★★ | keys |
| **P7 Science & workspace** | Self-testing comparator, notes, reports, discovery, CSV/repo inputs | ★★★ | — |
| **P8 Console** | The full instrument panel in the browser | ★★★ | — |
| **P9 The game** | Region, Oak's Lab, Gym battles, evolutions — all bound to events | ★★★★ | — |
| **P10 Remote + phone** | Kaggle/Colab jobs; the Pokégear phone app with voice redirect | ★★★ | Kaggle/Colab |
| **P11 More papers** | Four gyms with four reproductions | ★★★★ | 🔥 |
| **P12 Hardening** | Chaos-tested, measured, rehearsed, with a labelled replay fallback | ★★★ | 🔥 |

🔥 = **plug in the charger and switch to Performance mode** (runs are 3–3.5× slower on battery — measured). Close memory-hungry tabs: RAM, not the GPU, is our tightest resource.

## 9. The few numbers worth remembering (all measured on this laptop)

- Grokking reproduction (Nanda setup) on the GPU: **~62 s** plugged in (181 s on battery).
- A fast grokking variant: **4 s**; two at once: **7.2 s each**.
- A warm worker starts training **~10 ms** after receiving a job (vs ~2 s for a fresh process).
- Distillation experiment end-to-end: **~49 s**. Tiny NeRF 1 000 iterations: **~3.3 min** (PSNR 22 dB; without positional encoding it collapses).
- Materials baseline (Matbench `expt_gap`, Magpie + random forest): **MAE 0.447 eV in 58 s** on the CPU.
- LLM calls: **0.4–7 s**; the gateway allows ~10 quick calls before a 60-second penalty → the router spreads load and uses Groq as overflow.
- Daily LLM budget: **800 k tokens**, reset at 05:30 IST (fresh before judging).

## 10. Things that will bite if forgotten

1. The Elevate gateway **does not support tool-calling** — agents use our own `<thought>/<action>/<final>` text protocol.
2. Groq blocks Python's default User-Agent — always send a custom one.
3. Campus Wi-Fi blocks some sites; **download everything in advance** (`just fetch`), use the hotspot when needed.
4. Battery mode makes everything 3× slower — the HUD warns you.
5. Only **one Python venv** (disk has 36 GB free; torch is ~3 GB).
6. The benchmark scripts that produced every measured number live in `scripts/reference/` (copied out of `/tmp`, which is wiped on reboot).
7. Next.js 16 differs from what models were trained on — read the bundled docs before changing Next config.
8. Never show a replay as live. Never put a number on screen that isn't in `var/reports/`.
