from __future__ import annotations

import csv
import json
from pathlib import Path

from backend.app.models import (
    BlockedPair,
    Mentor,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    ScenarioInput,
    ScenarioSettings,
    SolverWeights,
)


ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "examples"


def build_demo_scenario() -> ScenarioInput:
    mentors: list[Mentor] = []

    for index in range(1, 41):
        mentors.append(
            Mentor(
                id=f"ON{index:02d}",
                name=f"One Normal {index:02d}",
                category=MentorCategory.NORMAL,
                participation=ParticipationKind.ONE_PERIOD,
                preferred_period=1 if index <= 20 else 2,
                gender="woman" if index % 2 else "man",
                year=str((index % 4) + 1),
                normal_subrole=(
                    NormalSubrole.INTERNATIONAL
                    if index in {1, 2, 21, 22}
                    else NormalSubrole.EVENT
                    if index in {6, 17, 28, 35}
                    else NormalSubrole.NORMAL
                ),
                requested_with=[f"TN{((index - 1) % 53) + 1:03d}"],
            )
        )

    for index in range(1, 54):
        mentors.append(
            Mentor(
                id=f"TN{index:03d}",
                name=f"Two Normal {index:03d}",
                category=MentorCategory.NORMAL,
                participation=ParticipationKind.TWO_PERIOD,
                gender="woman" if index % 2 else "man",
                year=str((index % 5) + 1),
                normal_subrole=(
                    NormalSubrole.INTERNATIONAL
                    if index in {1, 2, 3, 4, 5, 6, 11, 12, 30}
                    else NormalSubrole.EVENT
                    if index in {8, 19, 31, 44, 49, 53}
                    else NormalSubrole.NORMAL
                ),
                requested_with=[f"TN{(index % 53) + 1:03d}"] if index % 7 else [f"ON{((index - 1) % 40) + 1:02d}"],
            )
        )

    for index in range(1, 9):
        mentors.append(
            Mentor(
                id=f"SX{index:02d}",
                name=f"Sexi Mentor {index:02d}",
                category=MentorCategory.SEXI,
                participation=ParticipationKind.ONE_PERIOD if index <= 4 else ParticipationKind.TWO_PERIOD,
                preferred_period=index if index <= 2 else 2 if index <= 4 else None,
                gender="woman" if index % 2 else "man",
                year=str((index % 4) + 1),
                requested_with=[f"ON{index:02d}"] if index <= 4 else [],
            )
        )

    for index in range(1, 21):
        mentors.append(
            Mentor(
                id=f"HV{index:02d}",
                name=f"Hovding {index:02d}",
                category=MentorCategory.HOVDING,
                participation=ParticipationKind.TWO_PERIOD,
                gender="woman" if index % 2 else "man",
                year="leader",
                requested_with=[f"TN{index:03d}"] if index <= 10 else [],
            )
        )

    blocked_pairs = [
        BlockedPair(mentor_a="TN001", mentor_b="TN003"),
        BlockedPair(mentor_a="TN010", mentor_b="TN013"),
        BlockedPair(mentor_a="ON03", mentor_b="ON04"),
        BlockedPair(mentor_a="HV01", mentor_b="TN004"),
        BlockedPair(mentor_a="SX01", mentor_b="TN020"),
        BlockedPair(mentor_a="HV10", mentor_b="HV11"),
        BlockedPair(mentor_a="ON26", mentor_b="TN025"),
        BlockedPair(mentor_a="TN050", mentor_b="TN053"),
        BlockedPair(mentor_a="SX06", mentor_b="HV19"),
    ]

    return ScenarioInput(
        mentors=mentors,
        blocked_pairs=blocked_pairs,
        settings=ScenarioSettings(),
        weights=SolverWeights(),
    )


def build_tight_scenario() -> ScenarioInput:
    scenario = build_demo_scenario()
    updated_mentors = []
    extra_event_ids = {"TN040", "TN041", "TN042", "TN043", "TN044", "TN045"}
    for mentor in scenario.mentors:
        if mentor.id in extra_event_ids:
            updated_mentors.append(mentor.model_copy(update={"normal_subrole": NormalSubrole.EVENT}))
        else:
            updated_mentors.append(mentor)
    return scenario.model_copy(
        update={
            "mentors": updated_mentors,
            "settings": scenario.settings.model_copy(update={"international_extra_mentors": 4}),
        }
    )


def write_mentors_csv(path: Path, mentors: list[Mentor]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "id",
                "name",
                "category",
                "participation",
                "preferred_period",
                "gender",
                "year",
                "normal_subrole",
                "requested_with",
            ],
        )
        writer.writeheader()
        for mentor in mentors:
            writer.writerow(
                {
                    "id": mentor.id,
                    "name": mentor.name,
                    "category": mentor.category.value,
                    "participation": mentor.participation.value,
                    "preferred_period": mentor.preferred_period or "",
                    "gender": mentor.gender,
                    "year": mentor.year,
                    "normal_subrole": mentor.normal_subrole.value if mentor.normal_subrole else "",
                    "requested_with": ";".join(mentor.requested_with),
                }
            )


def write_blocked_pairs_csv(path: Path, blocked_pairs: list[BlockedPair]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["mentor_a", "mentor_b"])
        writer.writeheader()
        for pair in blocked_pairs:
            writer.writerow({"mentor_a": pair.mentor_a, "mentor_b": pair.mentor_b})


def write_scenario(path: Path, scenario: ScenarioInput) -> None:
    path.write_text(json.dumps(scenario.model_dump(mode="json"), indent=2), encoding="utf-8")


def write_manifest(path: Path, scenario_file: str, mentors_file: str, blocked_pairs_file: str, scenario: ScenarioInput) -> None:
    path.write_text(
        json.dumps(
            {
                "scenario": scenario_file,
                "mentors_csv": mentors_file,
                "blocked_pairs_csv": blocked_pairs_file,
                "mentor_count": len(scenario.mentors),
                "blocked_pair_count": len(scenario.blocked_pairs),
            },
            indent=2,
        ),
        encoding="utf-8",
    )


def main() -> None:
    EXAMPLES.mkdir(exist_ok=True)

    demo = build_demo_scenario()
    tight = build_tight_scenario()

    write_scenario(EXAMPLES / "demo_scenario.json", demo)
    write_mentors_csv(EXAMPLES / "demo_mentors.csv", demo.mentors)
    write_blocked_pairs_csv(EXAMPLES / "demo_blocked_pairs.csv", demo.blocked_pairs)
    write_manifest(EXAMPLES / "demo_manifest.json", "demo_scenario.json", "demo_mentors.csv", "demo_blocked_pairs.csv", demo)

    write_scenario(EXAMPLES / "tight_scenario.json", tight)
    write_mentors_csv(EXAMPLES / "tight_mentors.csv", tight.mentors)
    write_blocked_pairs_csv(EXAMPLES / "tight_blocked_pairs.csv", tight.blocked_pairs)
    write_manifest(EXAMPLES / "tight_manifest.json", "tight_scenario.json", "tight_mentors.csv", "tight_blocked_pairs.csv", tight)


if __name__ == "__main__":
    main()
