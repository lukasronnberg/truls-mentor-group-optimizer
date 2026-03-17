from __future__ import annotations

import json
from pathlib import Path

from backend.app.import_export import parse_blocked_pairs_csv, parse_mentors_csv
from backend.app.models import ScenarioInput


ROOT = Path(__file__).resolve().parents[1]
CONVERTED_DIR = ROOT / "data_raw" / "converted"
SCENARIO_PATH = CONVERTED_DIR / "scenario.json"
MENTORS_PATH = CONVERTED_DIR / "mentors.csv"
BLOCKED_PAIRS_PATH = CONVERTED_DIR / "blocked_pairs.csv"


def main() -> None:
    if not SCENARIO_PATH.exists():
        raise FileNotFoundError(f"Missing scenario file: {SCENARIO_PATH}")
    if not MENTORS_PATH.exists():
        raise FileNotFoundError(f"Missing mentors file: {MENTORS_PATH}")

    current = ScenarioInput.model_validate_json(SCENARIO_PATH.read_text(encoding="utf-8"))
    mentors = parse_mentors_csv(MENTORS_PATH.read_text(encoding="utf-8"))
    blocked_pairs = (
        parse_blocked_pairs_csv(BLOCKED_PAIRS_PATH.read_text(encoding="utf-8"))
        if BLOCKED_PAIRS_PATH.exists()
        else []
    )
    updated = current.model_copy(update={"mentors": mentors, "blocked_pairs": blocked_pairs})
    SCENARIO_PATH.write_text(
        json.dumps(updated.model_dump(mode="json"), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"Synchronized {len(mentors)} mentors into {SCENARIO_PATH}")


if __name__ == "__main__":
    main()
