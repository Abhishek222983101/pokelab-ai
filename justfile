# PokéLab — all commands. Run `just` for the list.

set shell := ["bash", "-cu"]

default:
    @just --list

# --- setup ---

init:
    [ -f .env ] || cp .env.example .env
    python3 scripts/gen_secrets.py
    cd core && cargo build
    uv sync --project brain
    uv sync --project labml
    uv sync --project workers
    cd web && (command -v pnpm >/dev/null && pnpm i || npm i)

fetch:
    bash scripts/fetch_assets.sh
    bash scripts/fetch_datasets.sh
    bash scripts/fetch_papers.sh

atlases:
    python3 assets/build_atlases.py

contracts:
    uv run --project contracts python -m pokelab_contracts.export
    cd core && cargo test -p lab-contracts-check 2>/dev/null || true
    cd web && npx vitest run contracts 2>/dev/null || true

# --- running ---

up:
    cd core && cargo run -p labd --release

dev:
    cd core && cargo run -p labd &
    cd web && npm run dev

doctor:
    -cd core && cargo run -p labd -- doctor
    -cd brain && uv run python -m pokelab_brain.doctor

# --- testing ---

test:
    cd core && cargo test
    uv run --project brain pytest -q
    uv run --project labml pytest -q
    uv run --project workers pytest -q
    cd web && npx vitest run

e2e:
    uv run --project tests pytest tests/e2e -q

# --- ML / ops ---

library:
    uv run --project labml python -m pokelab_labml.cli library

labml:
    uv run --project labml python -m pokelab_labml.cli train-all

tunnel:
    cloudflared tunnel --no-autoupdate --protocol http2 --url http://localhost:7700

replay db:
    cd core && cargo run -p labd --release -- --replay {{db}}

docs:
    bash docs/build_docs.sh
