from __future__ import annotations

import csv
import io
import re

from .models import BlockedPair, GroupResult, Mentor, ScenarioInput


def parse_requested_with(raw_value: str | None) -> list[str]:
    if not raw_value:
        return []
    return [part.strip() for part in re.split(r"[;,|]", raw_value) if part.strip()]


def parse_mentors_csv(text: str) -> list[Mentor]:
    reader = csv.DictReader(io.StringIO(text))
    mentors: list[Mentor] = []
    required_columns = {"id", "name", "category", "participation"}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        missing = sorted(required_columns - set(reader.fieldnames or []))
        raise ValueError(f"Mentor CSV is missing required columns: {', '.join(missing)}.")

    for row_number, row in enumerate(reader, start=2):
        try:
            mentors.append(
                Mentor.model_validate(
                    {
                        "id": row.get("id", ""),
                        "name": row.get("name", ""),
                        "category": row.get("category") or "normal",
                        "participation": row.get("participation", ""),
                        "preferred_period": int(row["preferred_period"])
                        if row.get("preferred_period")
                        else None,
                        "gender": row.get("gender") or "unspecified",
                        "year": row.get("year") or "unknown",
                        "normal_subrole": row.get("normal_subrole") or None,
                        "requested_with": parse_requested_with(row.get("requested_with")),
                    }
                )
            )
        except Exception as exc:
            raise ValueError(f"Invalid mentor CSV row {row_number}: {exc}") from exc

    return mentors


def parse_blocked_pairs_csv(text: str) -> list[BlockedPair]:
    reader = csv.DictReader(io.StringIO(text))
    blocked_pairs: list[BlockedPair] = []
    required_columns = {"mentor_a", "mentor_b"}
    if not required_columns.issubset(set(reader.fieldnames or [])):
        missing = sorted(required_columns - set(reader.fieldnames or []))
        raise ValueError(f"Blocked-pairs CSV is missing required columns: {', '.join(missing)}.")

    for row_number, row in enumerate(reader, start=2):
        try:
            blocked_pairs.append(
                BlockedPair.model_validate(
                    {
                        "mentor_a": row.get("mentor_a", ""),
                        "mentor_b": row.get("mentor_b", ""),
                    }
                )
            )
        except Exception as exc:
            raise ValueError(f"Invalid blocked-pairs CSV row {row_number}: {exc}") from exc

    return blocked_pairs


def parse_scenario_json(text: str) -> ScenarioInput:
    return ScenarioInput.model_validate_json(text)


def groups_to_csv(groups: list[GroupResult]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=[
            "period",
            "group_number",
            "group_label",
            "is_international",
            "mentor_id",
            "mentor_name",
            "category",
            "participation",
            "gender",
            "year",
            "normal_subrole",
            "assigned_leader_role",
        ],
    )
    writer.writeheader()
    for group in groups:
        for mentor in group.mentors:
            writer.writerow(
                {
                    "period": group.period,
                    "group_number": group.group_number,
                    "group_label": group.label,
                    "is_international": group.is_international,
                    "mentor_id": mentor.id,
                    "mentor_name": mentor.name,
                    "category": mentor.category.value,
                    "participation": mentor.participation.value,
                    "gender": mentor.gender,
                    "year": mentor.year,
                    "normal_subrole": mentor.normal_subrole.value if mentor.normal_subrole else "",
                    "assigned_leader_role": mentor.assigned_leader_role.value
                    if mentor.assigned_leader_role
                    else "",
                }
            )
    return buffer.getvalue()
