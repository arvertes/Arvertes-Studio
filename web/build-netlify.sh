#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
node web/test-glb.mjs
node web/test-system.mjs
for module in web/*.mjs; do
  node --check "$module"
done
npm --prefix web ci --include=dev --ignore-scripts --no-audit --no-fund
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
cp web/index.html web/studio.css web/{studio,ui,office,library,pipeline,glb,system-panels}.mjs office_habblaud/roster.json "$output/"
mkdir -p "$output/fonts" "$output/licenses"
modules=web/node_modules
"$modules/.bin/esbuild" web/viewer.mjs --bundle --minify --format=esm --outfile="$output/viewer.mjs"
cp "$modules/three/LICENSE" "$output/licenses/three-MIT.txt"
cp "$modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2" "$output/fonts/inter.woff2"
cp "$modules/@fontsource-variable/space-grotesk/files/space-grotesk-latin-wght-normal.woff2" "$output/fonts/space-grotesk.woff2"
cp "$modules/@fontsource/jetbrains-mono/files/jetbrains-mono-latin-400-normal.woff2" "$output/fonts/jetbrains-mono.woff2"
cp "$modules/@fontsource-variable/inter/LICENSE" "$output/licenses/inter-OFL.txt"
cp "$modules/@fontsource-variable/space-grotesk/LICENSE" "$output/licenses/space-grotesk-OFL.txt"
cp "$modules/@fontsource/jetbrains-mono/LICENSE" "$output/licenses/jetbrains-mono-OFL.txt"
printf '%s\n' "Habblaud / Márcio Junior / MIT / $pin" > "$output/HABBLAUD-SOURCE.txt"
test -s "$output/index.html"
test -s "$output/office.html"
test -s "$output/HABBLAUD-LICENSE.txt"
mkdir -p web/dist
cp -R "$output/." web/dist/
