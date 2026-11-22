#!/usr/bin/env bash
set -euo pipefail
fixture="$(mktemp -d)"
server=""
trap 'if [[ -n "$server" ]]; then kill "$server" 2>/dev/null || true; fi; rm -rf "$fixture"' EXIT
adb install -r mobile/app/build/outputs/apk/debug/app-debug.apk
adb install -r mobile/app/build/outputs/apk/androidTest/debug/app-debug-androidTest.apk
python -m mobile.tests.session_fixture "$fixture/invitation" &
server=$!
for _ in {1..50}; do
    if [[ -s "$fixture/invitation" ]]; then break; fi
    sleep 0.2
done
test -s "$fixture/invitation"
adb shell am instrument -w -r -e invitation "$(cat "$fixture/invitation")" \
    com.arvertes.mobile.test/com.arvertes.mobile.LocalSessionTest | tee "$fixture/instrumentation"
grep -q 'ARVERTES_SESSION_OK' "$fixture/instrumentation"
wait "$server"
