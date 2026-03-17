from __future__ import annotations

from pathlib import Path

from .models import ScenarioInput


EXAMPLES_DIR = Path(__file__).resolve().parents[2] / "examples"
CONVERTED_DIR = Path(__file__).resolve().parents[2] / "data_raw" / "converted"
DEFAULT_SCENARIO_PATH = EXAMPLES_DIR / "demo_scenario.json"
USER_DEFAULT_SCENARIO_PATH = CONVERTED_DIR / "scenario.json"


def build_example_scenario() -> ScenarioInput:
    scenario_path = USER_DEFAULT_SCENARIO_PATH if USER_DEFAULT_SCENARIO_PATH.exists() else DEFAULT_SCENARIO_PATH
    return ScenarioInput.model_validate_json(scenario_path.read_text(encoding="utf-8"))
