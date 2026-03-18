from __future__ import annotations

import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RELEASE_DIR = ROOT / "release"
BUNDLE_DIR = RELEASE_DIR / "TRULS"
FRONTEND_DIR = ROOT / "frontend"
FRONTEND_DIST = FRONTEND_DIR / "dist"


BUNDLE_LAUNCHER = """#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "Python 3 is required to run TRULS."
  echo "Install Python 3.11+ and try again."
  exit 1
fi

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
python -m pip install --upgrade pip

if [ ! -x ".venv/bin/mentor-groups" ]; then
  pip install -e .
fi

exec .venv/bin/mentor-groups
"""


BUNDLE_README = """TRULS Share Bundle

How to run:
1. Make sure Python 3.11 or newer is installed.
2. Double-click "Start TRULS.command".
3. On first launch, the app creates a local virtual environment and installs dependencies.
4. TRULS then opens in your browser.

Notes:
- This bundle includes a prebuilt frontend, so Node.js is not required.
- Local saved state is stored in the hidden ".truls" folder inside this bundle.
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
            "*.egg-info",
        ),
    )


def build_share_bundle() -> Path:
    if not shutil.which("npm"):
        raise RuntimeError("npm is required to build the share bundle.")

    _run(["npm", "run", "build"], cwd=FRONTEND_DIR)

    if BUNDLE_DIR.exists():
        shutil.rmtree(BUNDLE_DIR)
    BUNDLE_DIR.mkdir(parents=True, exist_ok=True)

    _copy_tree(ROOT / "backend", BUNDLE_DIR / "backend")
    _copy_tree(ROOT / "examples", BUNDLE_DIR / "examples")

    (BUNDLE_DIR / "frontend").mkdir(parents=True, exist_ok=True)
    shutil.copytree(FRONTEND_DIST, BUNDLE_DIR / "frontend" / "dist")

    for filename in ("README.md", "LICENSE", "pyproject.toml"):
        shutil.copy2(ROOT / filename, BUNDLE_DIR / filename)

    (BUNDLE_DIR / ".gitignore").write_text(".venv/\n.truls/\n__pycache__/\n.DS_Store\n", encoding="utf-8")
    launcher_path = BUNDLE_DIR / "Start TRULS.command"
    launcher_path.write_text(BUNDLE_LAUNCHER, encoding="utf-8")
    launcher_path.chmod(0o755)
    (BUNDLE_DIR / "RUN FIRST.txt").write_text(BUNDLE_README, encoding="utf-8")

    return BUNDLE_DIR


def main() -> None:
    bundle_path = build_share_bundle()
    print(f"Built shareable TRULS bundle at {bundle_path}")


if __name__ == "__main__":
    main()
