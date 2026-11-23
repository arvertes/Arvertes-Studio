#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
node web/test-glb.mjs
node --check web/studio.mjs
temp="$(mktemp -d)"
trap 'rm -rf "$temp"' EXIT
pin=faa1a012b5fbf632c66dc6801c5383e53a542406
git init -q "$temp/upstream"
git -C "$temp/upstream" remote add origin https://github.com/marmottajr/habblaud.git
git -C "$temp/upstream" fetch --depth=1 origin "$pin"
git -C "$temp/upstream" checkout --detach FETCH_HEAD
python3 office_habblaud/prepare.py "$temp/upstream"
(
  cd "$temp/upstream"
  npm ci --ignore-scripts
  VITE_ARVERTES_STATIC_PREVIEW=1 npm run build:client -- --base=./
)
output="$temp/upstream/dist/client"
mv "$output/index.html" "$output/office.html"
cp "$temp/upstream/LICENSE" "$output/HABBLAUD-LICENSE.txt"
cp web/index.html web/studio.css web/studio.mjs web/glb.mjs office_habblaud/roster.json "$output/"
printf '%s\n' "Habblaud / Márcio Junior / MIT / $pin" > "$output/HABBLAUD-SOURCE.txt"
test -s "$output/index.html"
test -s "$output/office.html"
test -s "$output/HABBLAUD-LICENSE.txt"
mkdir -p web/dist
cp -R "$output/." web/dist/
