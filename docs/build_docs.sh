#!/usr/bin/env bash
# Concatenate docs/_parts/*.md (in order) into docs/SYSTEM-ARCHITECTURE.md
set -euo pipefail
cd "$(dirname "$0")"
order=(00-header 01-ps 02-concept 03-architecture 04-stack 05-core 06-brain 07-ml 08-papers 09-frontend 10-contracts 11-nfr 12-demo 13-build-a 13-build-b 14-refs)
{ for p in "${order[@]}"; do cat "_parts/$p.md"; printf '\n'; done; } > SYSTEM-ARCHITECTURE.md
wc -l SYSTEM-ARCHITECTURE.md
