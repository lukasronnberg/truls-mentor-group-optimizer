#!/bin/zsh
set -euo pipefail

cd "$(dirname "$0")"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate

if [ ! -x ".venv/bin/mentor-groups" ]; then
  pip install -e ".[dev]"
fi

exec .venv/bin/mentor-groups
