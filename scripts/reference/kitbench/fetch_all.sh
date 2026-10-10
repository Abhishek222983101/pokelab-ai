#!/usr/bin/env bash
# Fetch all datasets for the kit benchmarks into /home/arch-nitro/elevate-ps03/data/raw/<dataset>/
K=$(cd "$(dirname "$0")" && pwd)
R=/home/arch-nitro/elevate-ps03/data/raw
F="$K/fetch.sh"
(
  for f in train-images-idx3-ubyte.gz train-labels-idx1-ubyte.gz t10k-images-idx3-ubyte.gz t10k-labels-idx1-ubyte.gz; do
    bash "$F" "$R/mnist" "$f" "https://ossci-datasets.s3.amazonaws.com/mnist/$f" "http://yann.lecun.com/exdb/mnist/$f" "https://storage.googleapis.com/cvdf-datasets/mnist/$f"
  done
) &
bash "$F" "$R/tiny_nerf" tiny_nerf_data.npz \
  "http://cseweb.ucsd.edu/~viscomp/projects/LF/papers/ECCV20/nerf/tiny_nerf_data.npz" \
  "https://people.eecs.berkeley.edu/~bmild/nerf/tiny_nerf_data.npz" &
bash "$F" "$R/matbench_expt_gap" matbench_expt_gap.json.gz "https://ml.materialsproject.org/projects/matbench_expt_gap.json.gz" &
bash "$F" "$R/matbench_steels" matbench_steels.json.gz "https://ml.materialsproject.org/projects/matbench_steels.json.gz" &
wait
