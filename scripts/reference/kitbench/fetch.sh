#!/usr/bin/env bash
# usage: fetch.sh DEST_DIR FILENAME URL [URL...]
# Tries each mirror in order (no TLS bypass, hard per-attempt timeout). Prints one METRIC {json} line per attempt.
# Stops at the first attempt that returns HTTP 200 with a non-empty body.
dest=$1; name=$2; shift 2
mkdir -p "$dest"
for url in "$@"; do
  tmp="$dest/.$name.part"
  out=$(curl -sS -L --connect-timeout 15 --max-time 180 -o "$tmp" -w '%{http_code} %{size_download} %{time_total}' "$url" 2>&1)
  rc=$?
  code=$(echo "$out" | tail -1 | awk '{print $1}')
  size=$(echo "$out" | tail -1 | awk '{print $2}')
  wall=$(echo "$out" | tail -1 | awk '{print $3}')
  err=$(echo "$out" | grep -i 'curl:' | head -1 | tr '"' "'" | cut -c1-200)
  ok=false
  if [ $rc -eq 0 ] && [ "$code" = "200" ] && [ -s "$tmp" ]; then
    mv "$tmp" "$dest/$name"; ok=true
    sha=$(sha256sum "$dest/$name" | cut -c1-16)
  else
    rm -f "$tmp"; sha=""
  fi
  printf 'METRIC {"step":"download","file":"%s","url":"%s","ok":%s,"curl_rc":%d,"http_code":"%s","bytes":%s,"sha256_16":"%s","err":"%s","wall_s":%s}\n' \
    "$name" "$url" "$ok" "$rc" "$code" "${size:-0}" "$sha" "$err" "$wall"
  $ok && exit 0
done
exit 1
