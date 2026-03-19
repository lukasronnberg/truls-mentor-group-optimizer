from pathlib import Path

from backend.app.workspace_store import get_workspace_dir, get_workspace_file


def test_workspace_store_uses_env_override(monkeypatch, tmp_path):
    monkeypatch.setenv("TRULS_WORKSPACE_DIR", str(tmp_path / "custom-workspace"))

    workspace_dir = get_workspace_dir()
    workspace_file = get_workspace_file()

    assert workspace_dir == Path(tmp_path / "custom-workspace")
    assert workspace_file == Path(tmp_path / "custom-workspace" / "workspace.json")
