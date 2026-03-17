from __future__ import annotations

from pathlib import Path

from .models import ScenarioInput


EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
DEFAULT_SCENARIO_PATH = EXAMPLES_DIR / "demo_scenario.json"


def build_example_scenario() -> ScenarioInput:
    return ScenarioInput.model_validate_json(DEFAULT_SCENARIO_PATH.read_text(encoding="utf-8"))
