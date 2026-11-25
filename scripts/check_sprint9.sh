#!/usr/bin/env bash
# Paired acceptance on local checkouts with preinstalled executors.
set -euo pipefail
studio="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
agents="$(cd "${1:?Passe o checkout do Agents}" && pwd)"
blender="${2:?Passe o executável do Blender}"
studio_python="${STUDIO_PYTHON:-python}"
agents_python="${AGENTS_PYTHON:-python}"
export QT_QPA_PLATFORM=offscreen

(
  cd "$agents"
  "$agents_python" -m unittest discover -s tests -v
)
(
  cd "$studio"
  "$studio_python" -m unittest discover -s tests/unit -v
  "$studio_python" -m unittest discover -s tests/desktop -v
  bash web/build-netlify.sh
  "$studio_python" tests/integration/check_styled_character.py "$blender" --agents "$agents"
  if [[ -n "${ARVERTES_TEST_POSTGRES:-}" && -n "${ARVERTES_TEST_CHROMIUM:-}" ]]; then
    playwright_package="$("$studio_python" -c 'import pathlib,playwright; print(pathlib.Path(playwright.__file__).parent.parent)')"
    export PYTHONPATH="$agents:$playwright_package${PYTHONPATH:+:$PYTHONPATH}"
    "$agents_python" web/tests/backend_browser.py
    ARVERTES_TEST_CHARACTER_ACCEPTANCE="$("$studio_python" -c       'import json,sys; print(json.dumps(dict(zip(("agents","blender","python"),sys.argv[1:])),ensure_ascii=False))'       "$agents" "$blender" "$studio_python")" "$agents_python" web/tests/backend_browser.py
    "$studio_python" web/tests/browser.py --chromium "$ARVERTES_TEST_CHROMIUM"
  fi
)
