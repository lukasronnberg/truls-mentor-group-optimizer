from __future__ import annotations

import json
from pathlib import Path

from .example_data import build_example_scenario
from .models import WorkspaceState


ROOT = Path(__file__).resolve().parents[2]
WORKSPACE_DIR = ROOT / ".truls"
WORKSPACE_FILE = WORKSPACE_DIR / "workspace.json"


def load_workspace() -> WorkspaceState:
    if not WORKSPACE_FILE.exists():
        return WorkspaceState(scenario=build_example_scenario(), saved_proposals=[])
    return WorkspaceState.model_validate_json(WORKSPACE_FILE.read_text(encoding="utf-8"))


def save_workspace(workspace: WorkspaceState) -> WorkspaceState:
    WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
    payload = json.dumps(workspace.model_dump(mode="json"), ensure_ascii=True, indent=2)
    WORKSPACE_FILE.write_text(payload, encoding="utf-8")
    return workspace
