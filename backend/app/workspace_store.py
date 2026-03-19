from __future__ import annotations

import json
import os
from pathlib import Path

from .example_data import build_example_scenario
from .models import WorkspaceState


ROOT = Path(__file__).resolve().parents[2]


def get_workspace_dir() -> Path:
    configured = os.environ.get("TRULS_WORKSPACE_DIR", "").strip()
    if configured:
        return Path(configured).expanduser()
    return ROOT / ".truls"


def get_workspace_file() -> Path:
    return get_workspace_dir() / "workspace.json"


def load_workspace() -> WorkspaceState:
    workspace_file = get_workspace_file()
    if not workspace_file.exists():
        return WorkspaceState(scenario=build_example_scenario(), saved_proposals=[])
    return WorkspaceState.model_validate_json(workspace_file.read_text(encoding="utf-8"))


def save_workspace(workspace: WorkspaceState) -> WorkspaceState:
    workspace_dir = get_workspace_dir()
    workspace_file = get_workspace_file()
    workspace_dir.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(workspace.model_dump(mode="json"), ensure_ascii=True, indent=2)
    workspace_file.write_text(payload, encoding="utf-8")
    return workspace
