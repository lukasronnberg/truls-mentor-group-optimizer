from __future__ import annotations

import csv
import json
import re
import unicodedata
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from zipfile import ZipFile

from backend.app.models import (
    BlockedPair,
    Mentor,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    ScenarioInput,
    ScenarioSettings,
)


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data_raw"
OUTPUT_DIR = RAW_DIR / "converted"

NS = {
    "main": "http://schemas.openxmlformats.org/spreadsheetml/2006/main",
    "pkgrel": "http://schemas.openxmlformats.org/package/2006/relationships",
}

RESULT_OVERRIDES = {
    "freja linusson hahn": "Freja Linusson-Hahn",
    "albert ahnfeldt": "Albert Ahnfelt",
    "ana corloka": "Ana Corluka",
    "martin petterson": "Martin Pettersson",
    "jakob shishoo": "Jacob Shishoo",
    "ingrid wjikstrom": "Ingrid Wijkström",
    "erik svedman": "Erik Svedman Sundberg",
    "ana garcia": "Ana Garcia Andersson",
    "axel arlehov": "Axel Sjöqvist Arlehov",
    "freja linusson hahn intis bollplank tema hovding vanlig grupp": "Freja Linusson-Hahn",
}

PREFERRED_PERIOD_OVERRIDES = {
    "Axel Sjöqvist Arlehov": 1,
}


@dataclass
class ApplicantRecord:
    name: str
    source_file: str
    source_sheet: str
    role: str = ""
    year: str = "unknown"
    weeks: str = ""
    preferred_period_text: str = ""
    wishes: str = ""


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKD", value or "")
    value = "".join(ch for ch in value if not unicodedata.combining(ch))
    value = (
        value.replace("ø", "o")
        .replace("Ø", "o")
        .replace("ä", "a")
        .replace("å", "a")
        .replace("ö", "o")
        .replace("ü", "u")
    )
    value = value.lower()
    value = re.sub(r"[^a-z0-9\s-]", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def normalize_name(value: str) -> str:
    cleaned = re.sub(r"\([^)]*\)", " ", value or "")
    cleaned = re.sub(r"^\s*event\s*", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*-\s*event\s*$", " ", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip(" -")
    key = normalize_text(cleaned)
    return RESULT_OVERRIDES.get(key, cleaned).strip()


def slugify_name(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", normalize_text(value)).strip("-")


def col_to_index(cell_ref: str) -> int:
    letters = "".join(ch for ch in cell_ref if ch.isalpha())
    value = 0
    for ch in letters:
        value = value * 26 + (ord(ch.upper()) - 64)
    return value - 1


def read_shared_strings(zf: ZipFile) -> list[str]:
    try:
        root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    except KeyError:
        return []
    return [
        "".join(text.text or "" for text in item.iterfind(".//main:t", NS))
        for item in root.findall("main:si", NS)
    ]


def workbook_sheets(zf: ZipFile) -> list[tuple[str, str]]:
    workbook = ET.fromstring(zf.read("xl/workbook.xml"))
    rels = ET.fromstring(zf.read("xl/_rels/workbook.xml.rels"))
    rel_map = {
        rel.attrib["Id"]: rel.attrib["Target"]
        for rel in rels.findall("pkgrel:Relationship", NS)
    }
    result: list[tuple[str, str]] = []
    for sheet in workbook.find("main:sheets", NS):
        relationship_id = sheet.attrib[
            "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
        ]
        target = rel_map[relationship_id]
        if not target.startswith("xl/"):
            target = "xl/" + target.lstrip("/")
        result.append((sheet.attrib["name"], target))
    return result


def read_sheet(zf: ZipFile, target: str, shared_strings: list[str]) -> list[list[str]]:
    root = ET.fromstring(zf.read(target))
    sheet_data = root.find("main:sheetData", NS)
    rows: list[list[str]] = []
    if sheet_data is None:
        return rows
    for row in sheet_data.findall("main:row", NS):
        values: dict[int, str] = {}
        max_col = -1
        for cell in row.findall("main:c", NS):
            idx = col_to_index(cell.attrib.get("r", ""))
            max_col = max(max_col, idx)
            cell_type = cell.attrib.get("t")
            value_node = cell.find("main:v", NS)
            text = ""
            if cell_type == "s" and value_node is not None and value_node.text is not None:
                text = shared_strings[int(value_node.text)]
            elif cell_type == "inlineStr":
                inline = cell.find("main:is", NS)
                text = (
                    "".join(node.text or "" for node in inline.iterfind(".//main:t", NS))
                    if inline is not None
                    else ""
                )
            elif value_node is not None and value_node.text is not None:
                text = value_node.text
            values[idx] = text
        rows.append([values.get(i, "") for i in range(max_col + 1)] if max_col >= 0 else [])
    return rows


def load_workbook(path: Path) -> dict[str, list[list[str]]]:
    with ZipFile(path) as zf:
        shared_strings = read_shared_strings(zf)
        return {
            name: read_sheet(zf, target, shared_strings)
            for name, target in workbook_sheets(zf)
        }


def first_matching_index(header: list[str], patterns: list[str]) -> int | None:
    lowered = [(cell or "").strip().lower() for cell in header]
    for idx, cell in enumerate(lowered):
        if any(pattern in cell for pattern in patterns):
            return idx
    return None


def load_applicants() -> dict[str, ApplicantRecord]:
    applicants: dict[str, ApplicantRecord] = {}
    for file_name in ["Phadder & GrillI ansökan.xlsx", "PeppI & Høvding ansökan.xlsx"]:
        sheets = load_workbook(RAW_DIR / file_name)
        for sheet_name, rows in sheets.items():
            if not rows:
                continue
            header = rows[0]
            name_idx = first_matching_index(header, ["ange för- och efternamn", "what's your name?"])
            if name_idx is None:
                continue
            role_idx = first_matching_index(
                header,
                ["vilken roll söker du", "what role do you want to apply for", "which role do you apply for"],
            )
            year_idx = first_matching_index(header, ["vilken klass går du i?"])
            weeks_idx = first_matching_index(
                header, ["hur många perioder söker du", "how many weeks do you apply for"]
            )
            preferred_period_idx = first_matching_index(
                header,
                ["vilken period hade du helst velat ha", "would you rather be theme phadder or mission phadder"],
            )
            wishes_idx = first_matching_index(header, ["önska upp till tre personer", "name up to three people"])
            for row in rows[1:]:
                if name_idx >= len(row):
                    continue
                name = row[name_idx].strip()
                if not name:
                    continue
                key = normalize_text(normalize_name(name))
                current = applicants.get(
                    key,
                    ApplicantRecord(name=normalize_name(name), source_file=file_name, source_sheet=sheet_name),
                )
                updated = ApplicantRecord(
                    name=current.name or normalize_name(name),
                    source_file=current.source_file,
                    source_sheet=current.source_sheet,
                    role=current.role or (row[role_idx].strip() if role_idx is not None and role_idx < len(row) else ""),
                    year=current.year if current.year != "unknown" else (row[year_idx].strip() if year_idx is not None and year_idx < len(row) and row[year_idx].strip() else "unknown"),
                    weeks=current.weeks or (row[weeks_idx].strip() if weeks_idx is not None and weeks_idx < len(row) else ""),
                    preferred_period_text=current.preferred_period_text
                    or (
                        row[preferred_period_idx].strip()
                        if preferred_period_idx is not None and preferred_period_idx < len(row)
                        else ""
                    ),
                    wishes=current.wishes or (row[wishes_idx].strip() if wishes_idx is not None and wishes_idx < len(row) else ""),
                )
                applicants[key] = updated
    return applicants


@dataclass
class SelectedPerson:
    raw_value: str
    name: str
    category: MentorCategory
    participation: ParticipationKind
    normal_subrole: NormalSubrole | None
    preferred_period: int | None
    source_column: str
    sexi_period_value: str = ""


def infer_period(value: str) -> int | None:
    lowered = normalize_text(value)
    if "tema" in lowered or "theme" in lowered:
        return 1
    if "uppdrag" in lowered or "mission" in lowered:
        return 2
    return None


def selection_contains(value: str, token: str) -> bool:
    return token in normalize_text(value)


def load_selection() -> list[SelectedPerson]:
    rows = load_workbook(RAW_DIR / "RESULTAT.xlsx")["Blad1"]
    selected: list[SelectedPerson] = []
    seen_keys: set[tuple[str, str]] = set()

    def append_unique(person: SelectedPerson) -> None:
        key = (person.category.value, normalize_text(person.name))
        if key in seen_keys:
            return
        seen_keys.add(key)
        selected.append(person)

    for row in rows[1:]:
        hovding_raw = row[1].strip() if len(row) > 1 else ""
        if hovding_raw and not re.fullmatch(r"[0-9.]+", hovding_raw):
            append_unique(
                SelectedPerson(
                    raw_value=hovding_raw,
                    name=normalize_name(hovding_raw),
                    category=MentorCategory.HOVDING,
                    participation=ParticipationKind.TWO_PERIOD,
                    normal_subrole=None,
                    preferred_period=None,
                    source_column="hovding",
                )
            )

        one_raw = row[2].strip() if len(row) > 2 else ""
        if one_raw and not re.fullmatch(r"[0-9.]+", one_raw):
            name = normalize_name(one_raw)
            append_unique(
                SelectedPerson(
                    raw_value=one_raw,
                    name=name,
                    category=MentorCategory.NORMAL,
                    participation=ParticipationKind.ONE_PERIOD,
                    normal_subrole=(
                        NormalSubrole.INTERNATIONAL if selection_contains(one_raw, "intis") else NormalSubrole.NORMAL
                    ),
                    preferred_period=infer_period(one_raw),
                    source_column="phadder_one_period",
                )
            )

        two_raw = row[3].strip() if len(row) > 3 else ""
        if two_raw and not re.fullmatch(r"[0-9.]+", two_raw) and normalize_text(two_raw) != "t":
            subrole = NormalSubrole.NORMAL
            if selection_contains(two_raw, "event"):
                subrole = NormalSubrole.EVENT
            elif selection_contains(two_raw, "intis") or selection_contains(two_raw, "intis phadder"):
                subrole = NormalSubrole.INTERNATIONAL
            append_unique(
                SelectedPerson(
                    raw_value=two_raw,
                    name=normalize_name(two_raw),
                    category=MentorCategory.NORMAL,
                    participation=ParticipationKind.TWO_PERIOD,
                    normal_subrole=subrole,
                    preferred_period=None,
                    source_column="phadder_two_period",
                )
            )

        sexi_raw = row[5].strip() if len(row) > 5 else ""
        sexi_period = row[6].strip() if len(row) > 6 else ""
        if sexi_raw and not re.fullmatch(r"[0-9.]+", sexi_raw):
            append_unique(
                SelectedPerson(
                    raw_value=sexi_raw,
                    name=normalize_name(sexi_raw),
                    category=MentorCategory.SEXI,
                    participation=ParticipationKind.TWO_PERIOD if sexi_period == "2.0" else ParticipationKind.ONE_PERIOD,
                    normal_subrole=None,
                    preferred_period=None,
                    source_column="sexi",
                    sexi_period_value=sexi_period,
                )
            )
    return selected


def build_period_from_application(record: ApplicantRecord, fallback: int | None = None) -> int | None:
    explicit = infer_period(record.preferred_period_text)
    if explicit is not None:
        return explicit
    if fallback is not None:
        return fallback
    return 1


def extract_requested_ids(wishes: str, selected_name_to_id: dict[str, str], own_name: str) -> list[str]:
    normalized_wishes = normalize_text(wishes)
    matches: list[tuple[int, str]] = []
    for selected_name, mentor_id in selected_name_to_id.items():
        if normalize_text(selected_name) == normalize_text(own_name):
            continue
        marker = normalize_text(selected_name)
        position = normalized_wishes.find(marker)
        if position >= 0:
            matches.append((position, mentor_id))
    matches.sort(key=lambda item: item[0])
    unique: list[str] = []
    for _, mentor_id in matches:
        if mentor_id not in unique:
            unique.append(mentor_id)
        if len(unique) == 3:
            break
    return unique


def build_mentors() -> tuple[list[Mentor], list[str]]:
    applicants = load_applicants()
    selection = load_selection()
    mentors: list[Mentor] = []
    unresolved: list[str] = []
    name_to_id: dict[str, str] = {}

    for person in selection:
        prefix = {
            MentorCategory.HOVDING: "hovding",
            MentorCategory.NORMAL: "normal",
            MentorCategory.SEXI: "sexi",
        }[person.category]
        mentor_id = f"{prefix}-{slugify_name(person.name)}"
        suffix = 2
        while mentor_id in name_to_id.values():
            mentor_id = f"{prefix}-{slugify_name(person.name)}-{suffix}"
            suffix += 1
        name_to_id[person.name] = mentor_id

    for person in selection:
        applicant = applicants.get(normalize_text(person.name))
        if applicant is None:
            unresolved.append(f"No application row found for {person.name} ({person.source_column}).")
            year = "unknown"
            wishes = ""
            preferred_period = person.preferred_period
        else:
            year = applicant.year or "unknown"
            wishes = applicant.wishes
            preferred_period = person.preferred_period
            if person.category == MentorCategory.SEXI and person.participation == ParticipationKind.ONE_PERIOD:
                preferred_period = build_period_from_application(applicant, fallback=1)
            elif person.category == MentorCategory.NORMAL and person.participation == ParticipationKind.ONE_PERIOD:
                preferred_period = build_period_from_application(applicant, fallback=person.preferred_period or 1)
        if person.name in PREFERRED_PERIOD_OVERRIDES:
            preferred_period = PREFERRED_PERIOD_OVERRIDES[person.name]

        mentors.append(
            Mentor(
                id=name_to_id[person.name],
                name=person.name,
                category=person.category,
                participation=person.participation,
                preferred_period=preferred_period,
                gender="unspecified",
                year=year if year else "unknown",
                normal_subrole=person.normal_subrole,
                requested_with=[],
            )
        )

    selected_name_to_id = {mentor.name: mentor.id for mentor in mentors}
    updated_mentors: list[Mentor] = []
    for mentor in mentors:
        applicant = applicants.get(normalize_text(mentor.name))
        wishes = applicant.wishes if applicant else ""
        requested_with = extract_requested_ids(wishes, selected_name_to_id, mentor.name)
        updated_mentors.append(mentor.model_copy(update={"requested_with": requested_with}))

    return updated_mentors, unresolved


def write_outputs(mentors: list[Mentor], unresolved: list[str]) -> None:
    OUTPUT_DIR.mkdir(exist_ok=True)
    settings = ScenarioSettings(
        groups_per_period=10,
        regular_group_quota_one_period=2,
        regular_group_quota_two_period=5,
        international_extra_mentors=3,
        international_group_numbers={1: 1, 2: 1},
    )
    scenario = ScenarioInput(
        mentors=mentors,
        blocked_pairs=[],
        settings=settings,
    )

    (OUTPUT_DIR / "scenario.json").write_text(
        json.dumps(scenario.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )

    with (OUTPUT_DIR / "mentors.csv").open("w", encoding="utf-8", newline="") as handle:
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

    with (OUTPUT_DIR / "blocked_pairs.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["mentor_a", "mentor_b"])
        writer.writeheader()
        for pair in []:
            writer.writerow({"mentor_a": pair.mentor_a, "mentor_b": pair.mentor_b})

    lines = [
        "# Converted Import Notes",
        "",
        "Outputs:",
        "",
        "- `scenario.json`",
        "- `mentors.csv`",
        "- `blocked_pairs.csv`",
        "",
        "Assumptions applied:",
        "",
        "- `Tema` -> period 1",
        "- `Uppdrag` -> period 2",
        "- `Axel Arlehov` -> `Axel Sjöqvist Arlehov`",
        "- `Freja Linusson Hahn (...)` -> `Freja Linusson-Hahn`",
        "- stray `T` row in the two-period column was ignored",
        "- duplicate `Lukas Doberhof` entry in the `SexI` column was deduplicated",
        "- `PeppI` and `GrillI` were ignored",
        "- no blocked pairs were available in the raw data, so export is empty",
        "- `gender` was not present in the workbooks and was set to `unspecified` for everyone",
        "",
        "Counts:",
        "",
        f"- total mentors: {len(mentors)}",
        f"- hovding: {sum(1 for mentor in mentors if mentor.category == MentorCategory.HOVDING)}",
        f"- normal one-period: {sum(1 for mentor in mentors if mentor.category == MentorCategory.NORMAL and mentor.participation == ParticipationKind.ONE_PERIOD)}",
        f"- normal two-period: {sum(1 for mentor in mentors if mentor.category == MentorCategory.NORMAL and mentor.participation == ParticipationKind.TWO_PERIOD)}",
        f"- sexi: {sum(1 for mentor in mentors if mentor.category == MentorCategory.SEXI)}",
        "",
        "Unresolved items:",
        "",
    ]
    if unresolved:
        lines.extend(f"- {item}" for item in unresolved)
    else:
        lines.append("- none")

    (OUTPUT_DIR / "conversion_notes.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    mentors, unresolved = build_mentors()
    write_outputs(mentors, unresolved)
    print(f"Wrote {len(mentors)} mentors to {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
