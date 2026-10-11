#!/bin/bash
# Deploy the desk to https://pokelab-ai.vercel.app, pointed at the CURRENT tunnel to this laptop's labd.
# The Vercel site is static; it talks to labd (GPU, brain) through the tunnel, so it is only "live" while
# this laptop + `just live` + the tunnel are running. Re-run this whenever the tunnel address changes.
set -e
cd "$(dirname "$0")/.."
URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/tunnel.log | tail -1)
[ -z "$URL" ] && { echo "no tunnel: run  cloudflared tunnel --no-autoupdate --protocol http2 --url http://localhost:7700 > /tmp/tunnel.log 2>&1 &"; exit 1; }
HOST=${URL#https://}
echo "backend host: $HOST"
D=$(mktemp -d)
( cd web && NEXT_PUBLIC_BACKEND_HOST=$HOST npx next build >/dev/null && cp -r out/. "$D"/ && npx next build >/dev/null )  # 2nd build restores the local (same-origin) bundle
cd "$D"
vercel link --yes --project pokelab-ai >/dev/null && rm -f .env.local
DEP=$(vercel deploy --prod --yes 2>&1 | grep -o 'https://pokelab-[a-z0-9]*-[a-z0-9-]*\.vercel\.app' | head -1)
vercel alias set "$DEP" pokelab-ai.vercel.app
echo "LIVE: https://pokelab-ai.vercel.app/lab/"
