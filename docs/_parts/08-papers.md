# PART 8 — WORKERS, KITS & THE PAPERS

## 8.1 Workers and kits

- **Kit job** (trusted, verified code in `workers/pokelab_workers/kits/`): runs inside a warm worker; starts in ~10 ms `[MEASURED]`. Agents *configure* kits (choosing every hyper-parameter, variant and what-if) and can *extend* them through script jobs.
- **Script job** (agent-written code): fresh `python` process in the project workspace, scrubbed env, wall-clock limit; must print JSON lines (the prompt gives the 6-line `emit()` helper to paste) — or the regex shim of `script_runner.py` converts `print`-style metrics.
- **Kit contract** (`kits/base.py`): `KitSpec{name, version, Config (pydantic), target_metric, direction, threshold_from_claim(claim) -> float, default_budget, telemetry_keys}`, `run(cfg, emit, stop, run_dir)`, `analyze(run_dir) -> artifacts`. Each kit ships CPU-tiny defaults for tests.

`[DECISION D-07]` Why kits at all, when "the agents should implement the paper"? Because a live demo cannot depend on an LLM writing a correct training loop from scratch in 60 s — and because the PS asks the system to **retain and reuse** what it learned. The kits are the lab's *skill library*: each was first produced during the build by the lab's own implement/debug loop and then human-verified (`source: verified`). In the demo, agents still read the paper, extract the spec, choose configurations, write the what-if variants, and handle failures; new papers without a kit go through script jobs (AC-24).

## 8.2 Gym 1 — Grokking (CPU-scale ML) · Modulo City · Sabrina `[HERO]`

| | |
|---|---|
| Papers | Power et al. 2022 (arXiv 2201.02177) — the PS's suggested paper; Nanda et al. 2023 (arXiv 2301.05217) — the standard fast setup |
| **Key result (claim)** | Small transformers on modular arithmetic **fit the training set in < 10³ steps, but generalise to the test set only after ~10⁵–10⁶ steps** (Power, Fig. 1, x/y mod 97, 50 % data, 10⁶-step budget, *Adam, no weight decay*); **weight decay is the most effective intervention** (Power, Fig. 2: more than halves the samples needed). Nanda: 1-layer transformer, p = 113, 30 % data, full-batch AdamW lr 1e-3 wd 1, 40 k epochs; test accuracy ≈ 100 % after ~10 k epochs (mainline seed: memorisation 0–1.4 k, circuit formation 1.4–9.4 k, clean-up 9.4–14 k) `[RESEARCH]` |
| Our reproduction | Nanda config on the RTX 5050: train acc ≥ 0.99 by step ~500; **test acc ≥ 0.95 at step 19 800, 62 s; 100 % by ~30 k steps / 94 s** `[MEASURED, plugged in]`. Power-style 2-layer minibatch config as a second claim (budget 10⁵ steps → Kaggle/Colab via the Router) |
| Verdict expectation | `REPRODUCED` (qualitative: delayed generalisation) with a quantitative difference (our grok step ≈ 2× Nanda's mainline seed) → the comparator must explain it (seed variance, init, implementation details) |
| **What-ifs** | (1) **wd = 0** → no grokking within budget `[MEASURED: test acc 0.00–0.36 at budget]` — and the twist that Power's own Fig. 1 *did* grok without weight decay at ~10⁶ steps (Adam, minibatch noise) → great comparator content; (2) **Navigator map** over log wd × train fraction; (3) Grokfast-EMA on/off (`[MEASURED]` ×1.15 on the transformer — smaller than the paper's ×50 on a different setup: another comparator story); (4) float64 softmax / StableMax for wd = 0 (Prieto et al.) `[STRETCH]` |
| Difference checklist (17) | optimizer regime (Adam wd0 vs AdamW wd1) · AdamW vs Adam+L2 · steps vs epochs (Power minibatch ≈ 10 steps/epoch at 50 % of 9 312) · budget truncation · seed variance (single-run outcomes flip with thread count/device — Ootani 2026) · data-fraction sensitivity (−1 % data ⇒ +40–50 % time near 25–30 %) · dataset definition (y≠0 for division; p 97 vs 113) · precision & softmax collapse · Adam ε · architecture/tokenisation (5 vs 3 tokens, LayerNorm) · init scale (Omnigrok) · which params get wd · LR/warm-up window · metric thresholds (99 % vs 95 %) · regularisers (dropout/noise) · paper errata (Nanda's wd timing text vs numbers) · hardware/determinism |
| Analyst | `grok_fourier`: key frequencies (Nanda's mainline: k ∈ {14, 35, 41, 42, 52}), restricted/excluded loss, Gini, weight norm |
| Oracle data | curve library §7.1.4 (330+ runs) |
| Data | generated (no download) |

## 8.3 Gym 2 — Knowledge distillation (Edge & efficient ML) · Edge Port · Lt. Surge

| | |
|---|---|
| Paper | Hinton, Vinyals & Dean 2015, *Distilling the Knowledge in a Neural Network* (arXiv 1503.02531) |
| **Key result (claim, verified)** | MNIST: teacher 784-1200-1200-10 (dropout, weight constraints, 2-px jitter) → **67 test errors**; student 784-800-800-10 trained on hard labels without regularisation → **146 errors**; same student trained to match the teacher's soft targets at **T = 20** → **74 errors**. Small students (30 units/layer) work best at **T ≈ 2.5–4**. **Omitting all 3s** from the transfer set → 206 errors (133 on the 1 010 test 3s); after raising the 3-bias by 3.5 → **109 errors, 98.6 % of 3s correct**. Transfer set of only 7s and 8s → 47.3 % errors → 13.2 % after bias correction |
| Our reproduction `[MEASURED, AC, single seed]` | teacher (30 epochs, dropout) **119** errors; hard-label student **140**; **KD T = 4: 122**; KD T = 20: 129 — whole script **49 s**. The *effect* reproduces (KD closes 18 of the 21-error gap); absolute numbers differ (no jitter augmentation, no weight constraints, short training) → comparator material |
| Targets for P11.1 | ≥ 3 seeds; add 2-px jitter to the teacher to approach 67; report mean ± CI |
| **What-ifs** | (1) temperature sweep T ∈ {1, 2, 4, 8, 20} × student width {30, 800} (paper: wide students insensitive above 8, tiny students prefer 2.5–4; `[MEASURED]` tiny 784-30-10 student got worse at T = 20); (2) **omitted-digit transfer** + bias correction (reproduces the "mythical digit" result); (3) α (hard/soft weight) sweep |
| Difference checklist | teacher strength (jitter, max-norm, epochs) · student regularisation · T and α · the T² gradient scaling · transfer set (train vs unlabeled) · epochs/early stopping · seeds · learning-rate schedule |
| Analyst | `kd_darkknowledge`: soft-target entropy vs T, student–teacher agreement, per-class errors |
| Data | MNIST — `data/raw/mnist/` (from `ossci-datasets.s3.amazonaws.com/mnist/`, MD5 matches torchvision) `[MEASURED]` |

## 8.4 Gym 3 — Tiny NeRF (3D) · Lumen Town · Blaine

| | |
|---|---|
| Paper | Mildenhall et al. 2020, *NeRF* (arXiv 2003.08934), as the PS's low-resolution "tiny NeRF" |
| **Key result (claim, verified)** | Full model on Realistic Synthetic 360°: **PSNR 31.01**; ablation Table 2 row 1 (no positional encoding, no view dependence, no hierarchical sampling): **26.67** — positional encoding is what lets the MLP represent high-frequency detail ("removing the positional encoding drastically decreases the model's ability to represent high frequency geometry and texture") |
| Our reproduction `[MEASURED, AC]` | tiny NeRF (lego, 100×100, 106 views, 8×256 MLP, 64 samples, L = 6, bf16): held-out PSNR **14.4 @100 → 19.5 @300 → 21.2 @500 → 22.0 @1000 iters** (197 ms/iter, 3.3 min). Rendering a 100×100 view: 78 ms (bf16) → a 120-frame spin in 9.4 s |
| **What-if** | **No positional encoding (L = 0)**: seed 0 collapsed to an all-black image (9.39 dB) for 1 000 iters; seed 1: 15.9 dB @300 vs 19.5 with PE → the effect reproduces, with a failure mode the paper does not report (collapse) → comparator material. Also: L ∈ {2, 4, 6, 10}; samples 32 vs 64 |
| Demo sizing | Live: 300 iterations (~60 s) — enough to show the PE gap; the full 1 000-iteration run and the spin video come from the library (labelled) |
| Difference checklist | resolution (100² vs 800²) · scene (lego only) · no hierarchical sampling / view dependence in tiny NeRF · iterations · precision (bf16) · seeds · near/far bounds · white vs black background |
| Analyst | `nerf_spectrum`: per-view PSNR, 2D FFT energy of renders vs ground truth (high-frequency energy missing without PE — spectral bias, the same Fourier story as grokking) |
| Data | `data/raw/tiny_nerf/tiny_nerf_data.npz` (12.7 MB, sha256 `3887ad58…7c3356`; source is plain HTTP and slow — keep the local copy) |

## 8.5 Gym 4 — Matbench (Materials science) · Crystal Cave · Brock

| | |
|---|---|
| Paper | Dunn et al. 2020, *Benchmarking materials property prediction methods: the Matbench test set and Automatminer reference algorithm* (npj Comput. Mater.) |
| **Key result (claim, verified from the official leaderboard)** | `matbench_expt_gap` (4 604 compositions, experimental band gap): **RF-SCM/Magpie MAE 0.4461 ± 0.0177 eV**, Dummy (mean) **1.1435**; composition-attention models do better: CrabNet 0.3463, MODNet 0.3327. `matbench_steels` (312 alloys, yield strength): **RF-SCM/Magpie 103.51 ± 11.04 MPa**, Dummy 229.74, best TPOT-Mat 79.95 |
| Our reproduction `[MEASURED, CPU, 5-fold matbench split]` | expt_gap: **Magpie + RF 0.447 ± 0.018 eV** (paper 0.4461 ± 0.0177 → reproduced), element fractions + RF 0.476, mean baseline **1.144** (paper 1.1435). steels: Magpie + RF 104.3 ± 10.2 (paper 103.5), **fractions + RF 90.7 ± 7.8** (beats the paper's baseline — a "what-if" finding), mean 229.7 (paper 229.74). Total < 1 min on CPU |
| **What-ifs** | (1) **Roost/CrabNet-style composition attention** (the PS's Roost paper, Goodall & Lee 2020) vs the RF baseline — target region 0.33–0.38 eV on expt_gap (leaderboard) — this is the "**new capability needed**" moment: no agent covers `materials_featurize` → Eevee spawn → evolves to Vaporeon; (2) learning curve vs training-set size; (3) feature set ablation (fractions vs Magpie) |
| Difference checklist | featurizer version (matminer Magpie preset) · RF size (500 trees in the paper's config vs 300 ours) · nested CV vs plain CV · dataset version (matbench v0.1) · NaN-feature handling · seeds |
| Analyst | `materials_parity`: parity plot, MAE by element family, learning curve |
| Data | `data/raw/matbench_expt_gap/matbench_expt_gap.json.gz`, `data/raw/matbench_steels/…` (from `ml.materialsproject.org/projects/`) `[MEASURED]`; matminer 0.10.1 installs in a Python 3.12 venv (note: one PyPI dependency timed out once — fetch on a good network) |

## 8.6 Arena — fair comparison (Grinsztajn et al. 2022) · Erika `[PS-D12, D2]`

| | |
|---|---|
| Paper | Grinsztajn, Oyallon & Varoquaux, *Why do tree-based models still outperform deep learning on typical tabular data?* (NeurIPS 2022 D&B, arXiv 2207.08815) |
| **Key result (claim, verified)** | On a curated benchmark of **45 datasets**, tree-based models (XGBoost, RF, GBT) remain state of the art on **medium-sized data (~10 k samples)**, for every random-search budget. Mechanisms: NNs are hurt by **uninformative features** (adding them widens the gap) and are **rotation-invariant** — a random rotation of the features *reverses* the ranking (NNs above trees); NNs are biased toward smooth/low-frequency functions (spectral bias — the same Fourier story as grokking and NeRF) |
| Our reproduction `[MEASURED, CPU, 1 seed, 70/30 split]` | **Base:** trees win — electricity RF 0.880 / HGB 0.861 vs MLP 0.818; california HGB 0.904 vs MLP 0.874; MagicTelescope 0.865 vs 0.861; credit ≈ tie. **+ uninformative features (×2 Gaussian columns):** gap widens — california MLP 0.874 → 0.844 (trees 0.904 → 0.899). **Random rotation:** ranking **reverses** — california MLP 0.872 > HGB 0.849; credit MLP 0.745 > HGB 0.709; MagicTelescope MLP 0.851 > HGB 0.848. Every model < 10 s except the MLP on electricity (40–52 s) |
| Use | The **comparison template** showcase (two approaches, identical splits/seeds/budgets, paired comparison, verdict with CIs) and the **"bring your own CSV"** path (AC-24) |
| **What-ifs** | (1) uninformative-feature injection (k × noise columns); (2) random rotation; (3) training-set size sweep; (4) hyper-parameter budget (random-search iterations) per model |
| Difference checklist | per-dataset preprocessing (quantile transform, truncation to 10 k train samples in the paper) · hyper-parameter search budget (paper: up to 20 000 compute-hours of random search vs our defaults) · model zoo (paper adds ResNet, FT-Transformer, SAINT) · seeds/splits · metric (accuracy vs R²) |
| Data | `data/raw/tabular/{MagicTelescope, electricity, california, credit}.csv` (HF `inria-soda/tabular-benchmark`, `clf_num/`, 0.8–2.5 MB each, sha256 in `SHA256SUMS`) `[MEASURED]` |
| Reference script | `scripts/reference/kitbench/arena_quick.py` |

## 8.7 Kits summary (what P2/P11 build)

| Kit | Device | Live run length (demo config) `[MEASURED]` | Library runs for the Oracle | Analyst |
|---|---|---|---|---|
| `grokking` (nanda/power/mlp variants) | GPU | 4 s (MLP) … 62 s (Nanda) | 330+ | `grok_fourier` |
| `distill` | GPU | ~49 s full script (teacher cached after first run → students ~10–13 s each) | 40+ | `kd_darkknowledge` |
| `nerf` | GPU | ~60 s for 300 iterations | 30+ (fewer: each run is minutes) | `nerf_spectrum` |
| `materials` | CPU worker | < 60 s | 60+ (cheap) | `materials_parity` |
| `arena` | CPU | < 10 s per model (MLP on electricity ~45 s) `[MEASURED]` | 40+ | — |
| `smoke` | any | 1 s | — | — |

## 8.8 Remote runners (Kaggle, Colab) `[PS-D3]`

- **Kaggle** (`remote/kaggle_runner.py`): build a kernel dir (kit code + config + JSON-lines entry + `kernel-metadata.json` with a **fresh slug per job**, `enable_gpu: true`, `machine_shape: NvidiaTeslaT4`), `kaggle kernels push -p <dir> --accelerator NvidiaTeslaT4`, **stream `kaggle kernels logs -f <user>/<slug>`** (Kaggle CLI 2.2.4 follows a running kernel's log → our JSON lines arrive *live*), with `kernels status` polling as a fallback and `kernels output` at the end for artifacts. `[MEASURED]` T4 + torch 2.11 cu128 worked; round trip ~40 s for a trivial job; quota 30 GPU-h/week.
- **Colab** (`remote/colab_runner.py`): `colab --auth oauth2 run --gpu T4 --timeout <budget_s> <script.py>` streams stdout live → forwarded line by line; on kill: `colab stop -s <session>`. ⚠️ `--timeout` **defaults to 30 s** (longer jobs are torn down and marked failed) — always pass it; ⚠️ an unknown `--gpu` value silently becomes A100 — validate against {T4, L4}; use `--config <per-job file>` to isolate sessions. `[MEASURED]` free Tesla T4, torch 2.11 cu130; session auto-stops.
- Both runners emit exactly the worker protocol (§10.5), so labd, the Oracle and the UI treat remote jobs like local ones (remote metrics may arrive in bursts on Kaggle).

## 8.9 Environment engineering `[PS-D4]`

- Kits run in the shared venv. Projects that need extra packages (e.g. matminer, a repo's requirements) get `var/workspaces/<project>/venv` created with `uv venv --python 3.12` + `uv pip install` (allowlist §11.4) — the Env Engineer agent (Bulbasaur) owns this, and every successful install recipe is saved to the fix library (so the second time is instant).
- Typical failures it must handle (seeded in the Bug Gym): missing package, incompatible torch build (cu wheels), CUDA unavailable → CPU fallback, version pins in old repos (e.g. pytorch-lightning in `openai/grok`), data path errors.

---
