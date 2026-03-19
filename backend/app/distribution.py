from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "release"
BUNDLE_DIR = RELEASE_DIR / "TRULS"
APP_DIR = RELEASE_DIR / "TRULS.app"
APP_CONTENTS_DIR = APP_DIR / "Contents"
APP_RESOURCES_DIR = APP_CONTENTS_DIR / "Resources"
APP_MACOS_DIR = APP_CONTENTS_DIR / "MacOS"
APP_SOURCE_DIR = APP_RESOURCES_DIR / "truls-source"
ZIP_PATH = RELEASE_DIR / "TRULS-macOS.zip"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"
ASSETS_DIR = ROOT / "assets"
APP_ICON_PATH = ASSETS_DIR / "TRULS.icns"


BUNDLE_LAUNCHER = """#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

EXPECTED_BUNDLE_VERSION="__TRULS_BUNDLE_VERSION__"
INSTALLED_VERSION_FILE=".truls-bundle-version"

pick_python() {
  local candidates=(
    /opt/homebrew/bin/python3.14
    /opt/homebrew/bin/python3.13
    /opt/homebrew/bin/python3.12
    /opt/homebrew/bin/python3.11
    /opt/homebrew/bin/python3
    /usr/local/bin/python3.14
    /usr/local/bin/python3.13
    /usr/local/bin/python3.12
    /usr/local/bin/python3.11
    /usr/local/bin/python3
    python3.14
    python3.13
    python3.12
    python3.11
    python3
  )
  for candidate in "${candidates[@]}"; do
    if [ ! -x "$candidate" ] && ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    local resolved="$candidate"
    if [ ! -x "$resolved" ]; then
      resolved="$(command -v "$candidate")"
    fi
    if "$resolved" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      echo "$resolved"
      return 0
    fi
  done
  return 1
}

PYTHON_BIN="$(pick_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  echo "TRULS requires Python 3.11 or newer."
  exit 1
fi

if [ -x ".venv/bin/python" ]; then
  if ! ".venv/bin/python" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
  then
    rm -rf ".venv"
  fi
fi

if [ ! -d ".venv" ]; then
  "$PYTHON_BIN" -m venv .venv
fi

source .venv/bin/activate
if [ ! -f "$INSTALLED_VERSION_FILE" ] || [ "$(cat "$INSTALLED_VERSION_FILE")" != "$EXPECTED_BUNDLE_VERSION" ] || [ ! -x ".venv/bin/mentor-groups" ]; then
  python -m pip install --upgrade pip
  pip install -e .
  printf '%s' "$EXPECTED_BUNDLE_VERSION" > "$INSTALLED_VERSION_FILE"
fi

exec .venv/bin/mentor-groups
"""


APP_LAUNCHER = """#!/bin/zsh
set -euo pipefail

APP_CONTENTS="$(cd "$(dirname "$0")/.." && pwd)"
APP_SOURCE="$APP_CONTENTS/Resources/truls-source"
SUPPORT_ROOT="$HOME/Library/Application Support/TRULS"
RUNTIME_ROOT="$SUPPORT_ROOT/runtime"
VENV_DIR="$RUNTIME_ROOT/.venv"
LOG_DIR="$SUPPORT_ROOT/logs"
LOG_FILE="$LOG_DIR/truls.log"
EXPECTED_BUNDLE_VERSION="__TRULS_BUNDLE_VERSION__"
INSTALLED_VERSION_FILE="$RUNTIME_ROOT/installed-bundle-version.txt"

mkdir -p "$RUNTIME_ROOT" "$LOG_DIR"

pick_python() {
  local candidates=(
    /opt/homebrew/bin/python3.14
    /opt/homebrew/bin/python3.13
    /opt/homebrew/bin/python3.12
    /opt/homebrew/bin/python3.11
    /opt/homebrew/bin/python3
    /usr/local/bin/python3.14
    /usr/local/bin/python3.13
    /usr/local/bin/python3.12
    /usr/local/bin/python3.11
    /usr/local/bin/python3
    python3.14
    python3.13
    python3.12
    python3.11
    python3
  )
  for candidate in "${candidates[@]}"; do
    if [ ! -x "$candidate" ] && ! command -v "$candidate" >/dev/null 2>&1; then
      continue
    fi
    local resolved="$candidate"
    if [ ! -x "$resolved" ]; then
      resolved="$(command -v "$candidate")"
    fi
    if "$resolved" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
    then
      echo "$resolved"
      return 0
    fi
  done
  return 1
}

show_error() {
  local message="$1"
  osascript -e "display dialog \"$message\" buttons {\"OK\"} default button \"OK\" with icon caution"
}

PYTHON_BIN="$(pick_python || true)"
if [ -z "$PYTHON_BIN" ]; then
  show_error "TRULS requires Python 3.11 or newer. Install Python and try again."
  exit 1
fi

if [ -x "$VENV_DIR/bin/python" ]; then
  if ! "$VENV_DIR/bin/python" - <<'PY' >/dev/null 2>&1
import sys
raise SystemExit(0 if sys.version_info >= (3, 11) else 1)
PY
  then
    rm -rf "$VENV_DIR"
  fi
fi

if [ ! -d "$VENV_DIR" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi

source "$VENV_DIR/bin/activate"
if [ ! -f "$RUNTIME_ROOT/source-path.txt" ] || [ "$(cat "$RUNTIME_ROOT/source-path.txt")" != "$APP_SOURCE" ] || [ ! -f "$INSTALLED_VERSION_FILE" ] || [ "$(cat "$INSTALLED_VERSION_FILE")" != "$EXPECTED_BUNDLE_VERSION" ]; then
  python -m pip install --upgrade pip >>"$LOG_FILE" 2>&1
  if ! pip install -e "$APP_SOURCE" >>"$LOG_FILE" 2>&1; then
    show_error "TRULS could not finish setup. Open $LOG_FILE for details."
    exit 1
  fi
  printf '%s' "$APP_SOURCE" > "$RUNTIME_ROOT/source-path.txt"
  printf '%s' "$EXPECTED_BUNDLE_VERSION" > "$INSTALLED_VERSION_FILE"
fi

export TRULS_WORKSPACE_DIR="$SUPPORT_ROOT/workspace"
exec "$VENV_DIR/bin/python" -m backend.app.launcher >>"$LOG_FILE" 2>&1
"""


APP_INFO_PLIST = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleDevelopmentRegion</key>
  <string>en</string>
  <key>CFBundleDisplayName</key>
  <string>TRULS</string>
  <key>CFBundleExecutable</key>
  <string>TRULS</string>
  <key>CFBundleIdentifier</key>
  <string>com.lukasronnberg.truls</string>
  <key>CFBundleIconFile</key>
  <string>TRULS.icns</string>
  <key>CFBundleInfoDictionaryVersion</key>
  <string>6.0</string>
  <key>CFBundleName</key>
  <string>TRULS</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>CFBundleVersion</key>
  <string>1</string>
  <key>LSMinimumSystemVersion</key>
  <string>12.0</string>
  <key>NSHighResolutionCapable</key>
  <true/>
</dict>
</plist>
"""


BUNDLE_README = """TRULS Share Bundle

Included outputs:
- TRULS.app
- TRULS-macOS.zip
- TRULS folder bundle with Start TRULS.command

Recommended option:
1. Send TRULS-macOS.zip to your friend.
2. They unzip it.
3. They move TRULS.app wherever they want.
4. On first run, right-click the app and choose Open.

Why right-click Open:
- This app is not Apple code-signed or notarized.
- Gatekeeper may block a normal double-click on first launch.

Runtime behavior:
- The app keeps its runtime files under ~/Library/Application Support/TRULS
- The app creates its own Python virtual environment there
- Node.js is not required because the frontend is already prebuilt

If Python is missing:
- Install Python 3.11 or newer, then launch TRULS again
"""


def _run(args: list[str], cwd: Path) -> None:
    subprocess.run(args, cwd=cwd, check=True)


def _copy_tree(source: Path, destination: Path) -> None:
    shutil.copytree(
        source,
        destination,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            "*.pyc",
            ".DS_Store",
            ".pytest_cache",
            ".mypy_cache",
            "node_modules",
            "dist",
            ".venv",
            ".truls",
            "data_raw",
            "release",
            "*.egg-info",
        ),
    )


def _build_frontend() -> None:
    if not shutil.which("npm"):
        raise RuntimeError("npm is required to build the macOS share bundle.")
    _run(["npm", "run", "build"], cwd=FRONTEND_DIR)


def _write_file(path: Path, content: str, executable: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    if executable:
        path.chmod(0o755)


def _bundle_version() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
        value = completed.stdout.strip()
        if value:
            return value
    except Exception:
        pass
    watched = [ROOT / "pyproject.toml", ROOT / "backend" / "app" / "distribution.py"]
    latest_mtime = max(path.stat().st_mtime for path in watched if path.exists())
    return str(int(latest_mtime))


def _render_launcher(template: str, bundle_version: str) -> str:
    return template.replace("__TRULS_BUNDLE_VERSION__", bundle_version)


def _populate_source_tree(destination_root: Path) -> None:
    _copy_tree(ROOT / "backend", destination_root / "backend")
    _copy_tree(ROOT / "examples", destination_root / "examples")
    shutil.copy2(ROOT / "README.md", destination_root / "README.md")
    shutil.copy2(ROOT / "LICENSE", destination_root / "LICENSE")
    shutil.copy2(ROOT / "pyproject.toml", destination_root / "pyproject.toml")
    (destination_root / "frontend").mkdir(parents=True, exist_ok=True)
    shutil.copytree(FRONTEND_DIST, destination_root / "frontend" / "dist")
    (destination_root / ".gitignore").write_text(".venv/\n.truls/\n__pycache__/\n.DS_Store\n", encoding="utf-8")


def build_share_bundle() -> Path:
    _build_frontend()
    bundle_version = _bundle_version()

    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    _populate_source_tree(BUNDLE_DIR)
    _write_file(BUNDLE_DIR / "Start TRULS.command", _render_launcher(BUNDLE_LAUNCHER, bundle_version), executable=True)
    _write_file(BUNDLE_DIR / "RUN FIRST.txt", BUNDLE_README)
    return BUNDLE_DIR


def build_macos_app() -> Path:
    bundle_dir = build_share_bundle()
    bundle_version = _bundle_version()

    if APP_DIR.exists():
        shutil.rmtree(APP_DIR)

    APP_MACOS_DIR.mkdir(parents=True, exist_ok=True)
    APP_RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

    _populate_source_tree(APP_SOURCE_DIR)
    _write_file(APP_CONTENTS_DIR / "Info.plist", APP_INFO_PLIST)
    _write_file(APP_MACOS_DIR / "TRULS", _render_launcher(APP_LAUNCHER, bundle_version), executable=True)
    if APP_ICON_PATH.exists():
        shutil.copy2(APP_ICON_PATH, APP_RESOURCES_DIR / "TRULS.icns")

    if ZIP_PATH.exists():
        ZIP_PATH.unlink()
    _run(["ditto", "-c", "-k", "--keepParent", str(APP_DIR), str(ZIP_PATH)], cwd=RELEASE_DIR)

    _write_file(RELEASE_DIR / "RUN FIRST.txt", BUNDLE_README)
    return APP_DIR


def main() -> None:
    app_path = build_macos_app()
    print(f"Built TRULS app bundle at {app_path}")
    print(f"Built zipped app at {ZIP_PATH}")


if __name__ == "__main__":
    main()
