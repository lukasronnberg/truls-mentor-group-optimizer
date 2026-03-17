from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class MentorCategory(str, Enum):
    NORMAL = "normal"
    SEXI = "sexi"
    HOVDING = "hovding"


class ParticipationKind(str, Enum):
    ONE_PERIOD = "one_period"
    TWO_PERIOD = "two_period"


class NormalSubrole(str, Enum):
    NORMAL = "normal"
    EVENT = "event"
    INTERNATIONAL = "international"


class LeaderRole(str, Enum):
    HEAD = "head"
    VICE = "vice"


class SolveStatus(str, Enum):
    OPTIMAL = "optimal"
    FEASIBLE = "feasible"
    INFEASIBLE = "infeasible"


class IssueSeverity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


class RuleKind(str, Enum):
    HARD = "hard"
    SOFT = "soft"


class RuleStatus(str, Enum):
    SATISFIED = "satisfied"
    PARTIALLY_SATISFIED = "partially_satisfied"
    VIOLATED = "violated"
    NOT_APPLICABLE = "not_applicable"


class Mentor(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    category: MentorCategory = MentorCategory.NORMAL
    participation: ParticipationKind
    preferred_period: int | None = Field(default=None, ge=1, le=2)
    gender: str = Field(default="unspecified", min_length=1)
    year: str = Field(default="unknown", min_length=1)
    normal_subrole: NormalSubrole | None = None
    requested_with: list[str] = Field(default_factory=list, max_length=3)

    @field_validator("requested_with")
    @classmethod
    def normalize_requested_with(cls, value: list[str]) -> list[str]:
        cleaned: list[str] = []
        seen: set[str] = set()
        for raw_id in value:
            mentor_id = raw_id.strip()
            if not mentor_id or mentor_id in seen:
                continue
            cleaned.append(mentor_id)
            seen.add(mentor_id)
        return cleaned

    @model_validator(mode="after")
    def validate_category_fields(self) -> "Mentor":
        if self.participation == ParticipationKind.TWO_PERIOD and self.preferred_period is not None:
            raise ValueError("Two-period mentors cannot define a preferred_period.")
        if self.participation == ParticipationKind.ONE_PERIOD and self.preferred_period is None:
            raise ValueError("One-period mentors must define preferred_period as 1 or 2.")

        if self.category == MentorCategory.NORMAL:
            if self.normal_subrole is None:
                self.normal_subrole = NormalSubrole.NORMAL
        elif self.normal_subrole is not None:
            raise ValueError("Only category=normal mentors may define normal_subrole.")

        if self.category == MentorCategory.HOVDING and self.participation != ParticipationKind.TWO_PERIOD:
            raise ValueError("Hovding mentors must participate in both periods.")

        return self

    @property
    def is_event(self) -> bool:
        return self.category == MentorCategory.NORMAL and self.normal_subrole == NormalSubrole.EVENT

    @property
    def prefers_international(self) -> bool:
        return (
            self.category == MentorCategory.NORMAL
            and self.normal_subrole == NormalSubrole.INTERNATIONAL
        )


class BlockedPair(BaseModel):
    mentor_a: str = Field(min_length=1)
    mentor_b: str = Field(min_length=1)

    @model_validator(mode="after")
    def validate_pair(self) -> "BlockedPair":
        if self.mentor_a == self.mentor_b:
            raise ValueError("Blocked pairs must contain two different mentor ids.")
        return self

    @property
    def normalized(self) -> tuple[str, str]:
        return tuple(sorted((self.mentor_a, self.mentor_b)))


class ScenarioSettings(BaseModel):
    period_count: int = 2
    groups_per_period: int = Field(default=10, ge=1)
    regular_group_quota_one_period: int = Field(default=2, ge=0)
    regular_group_quota_two_period: int = Field(default=5, ge=0)
    international_extra_mentors: int = Field(default=3, ge=0)
    international_group_numbers: dict[int, int] = Field(default_factory=lambda: {1: 1, 2: 1})
    ideal_max_event_mentors_per_group: int = Field(default=1, ge=0)
    absolute_max_event_mentors_per_group: int = Field(default=2, ge=0)
    max_solver_time_seconds: int = Field(default=20, ge=1, le=300)
    enforce_strict_quotas_when_feasible: bool = True

    @field_validator("period_count")
    @classmethod
    def validate_period_count(cls, value: int) -> int:
        if value != 2:
            raise ValueError("This application currently supports exactly 2 periods.")
        return value

    @field_validator("international_group_numbers", mode="before")
    @classmethod
    def normalize_international_group_numbers(
        cls, value: dict[int | str, int | str] | None
    ) -> dict[int, int]:
        if value is None:
            return {1: 1, 2: 1}
        return {int(period): int(group_number) for period, group_number in value.items()}

    @model_validator(mode="after")
    def validate_international_groups(self) -> "ScenarioSettings":
        expected_periods = set(range(1, self.period_count + 1))
        if set(self.international_group_numbers.keys()) != expected_periods:
            raise ValueError(
                f"international_group_numbers must contain keys {sorted(expected_periods)}."
            )
        for period, group_number in self.international_group_numbers.items():
            if not 1 <= group_number <= self.groups_per_period:
                raise ValueError(
                    f"International group for period {period} must be between 1 and "
                    f"{self.groups_per_period}."
                )
        if self.ideal_max_event_mentors_per_group > self.absolute_max_event_mentors_per_group:
            raise ValueError(
                "ideal_max_event_mentors_per_group cannot exceed "
                "absolute_max_event_mentors_per_group."
            )
        return self

    @property
    def total_group_slots(self) -> int:
        return self.period_count * self.groups_per_period

    @property
    def total_regular_normal_one_slots(self) -> int:
        return self.total_group_slots * self.regular_group_quota_one_period

    @property
    def ideal_distinct_normal_two_mentors(self) -> int:
        return (
            self.groups_per_period * self.regular_group_quota_two_period
            + self.international_extra_mentors
        )

    @property
    def distinct_leader_target(self) -> int:
        return self.groups_per_period * 2


class SolverWeights(BaseModel):
    quota_shortfall: int = Field(default=1_000_000, ge=0)
    quota_overflow: int = Field(default=850_000, ge=0)
    international_extra_two_period_shortfall: int = Field(default=80_000, ge=0)
    international_preference: int = Field(default=150_000, ge=0)
    nonpreferred_international: int = Field(default=20_000, ge=0)
    request_missing: int = Field(default=250_000, ge=0)
    preferred_period_miss: int = Field(default=8_000, ge=0)
    repeated_groupmates: int = Field(default=150, ge=0)
    event_second_mentor: int = Field(default=10_000, ge=0)
    event_evenness: int = Field(default=1_000, ge=0)
    sexi_evenness: int = Field(default=5_000, ge=0)
    balance_gender: int = Field(default=250, ge=0)
    balance_year: int = Field(default=250, ge=0)

    @classmethod
    def grouped_fields(cls) -> dict[str, list[str]]:
        return {
            "Quota and International": [
                "quota_shortfall",
                "quota_overflow",
                "international_extra_two_period_shortfall",
                "international_preference",
                "nonpreferred_international",
            ],
            "Preferences": [
                "request_missing",
                "preferred_period_miss",
                "repeated_groupmates",
            ],
            "Distribution": [
                "event_second_mentor",
                "event_evenness",
                "sexi_evenness",
                "balance_gender",
                "balance_year",
            ],
        }


class ScenarioInput(BaseModel):
    mentors: list[Mentor] = Field(default_factory=list)
    blocked_pairs: list[BlockedPair] = Field(default_factory=list)
    settings: ScenarioSettings = Field(default_factory=ScenarioSettings)
    weights: SolverWeights = Field(default_factory=SolverWeights)

    @model_validator(mode="after")
    def validate_cross_references(self) -> "ScenarioInput":
        mentor_ids = [mentor.id for mentor in self.mentors]
        duplicate_ids = sorted(
            {mentor_id for mentor_id in mentor_ids if mentor_ids.count(mentor_id) > 1}
        )
        if duplicate_ids:
            raise ValueError(f"Duplicate mentor ids are not allowed: {', '.join(duplicate_ids)}.")

        known_ids = set(mentor_ids)
        blocked_pair_set = {blocked_pair.normalized for blocked_pair in self.blocked_pairs}
        for mentor in self.mentors:
            unknown_requests = sorted(set(mentor.requested_with) - known_ids)
            if unknown_requests:
                raise ValueError(
                    f"Mentor {mentor.id} references unknown requested_with ids: "
                    f"{', '.join(unknown_requests)}."
                )
            if mentor.id in mentor.requested_with:
                raise ValueError(f"Mentor {mentor.id} cannot request themselves.")
            conflicting_requests = [
                requested_id
                for requested_id in mentor.requested_with
                if tuple(sorted((mentor.id, requested_id))) in blocked_pair_set
            ]
            if conflicting_requests:
                raise ValueError(
                    f"Mentor {mentor.id} requests blocked mentor(s): "
                    f"{', '.join(sorted(conflicting_requests))}."
                )

        seen_pairs: set[tuple[str, str]] = set()
        for blocked_pair in self.blocked_pairs:
            if blocked_pair.mentor_a not in known_ids or blocked_pair.mentor_b not in known_ids:
                raise ValueError(
                    f"Blocked pair ({blocked_pair.mentor_a}, {blocked_pair.mentor_b}) references "
                    "unknown mentor ids."
                )
            if blocked_pair.normalized in seen_pairs:
                raise ValueError(
                    f"Duplicate blocked pair detected: {blocked_pair.normalized[0]} / "
                    f"{blocked_pair.normalized[1]}."
                )
            seen_pairs.add(blocked_pair.normalized)

        return self


class ScenarioIssue(BaseModel):
    code: str
    severity: IssueSeverity
    message: str
    details: str | None = None


class ValidationSummary(BaseModel):
    mentor_count: int
    blocked_pair_count: int
    normal_one_period_supply: int
    normal_one_period_target: int
    normal_two_period_supply: int
    normal_two_period_target: int
    sexi_supply: int
    leader_supply: int
    leader_target: int
    event_assignment_supply: int
    event_ideal_capacity: int
    event_absolute_capacity: int
    international_preference_count: int


class ValidationResponse(BaseModel):
    ok: bool
    errors: list[ScenarioIssue] = Field(default_factory=list)
    warnings: list[ScenarioIssue] = Field(default_factory=list)
    summary: ValidationSummary


class AssignedMentor(BaseModel):
    id: str
    name: str
    category: MentorCategory
    participation: ParticipationKind
    gender: str
    year: str
    normal_subrole: NormalSubrole | None = None
    assigned_leader_role: LeaderRole | None = None
    requested_with: list[str] = Field(default_factory=list)


class GroupSummary(BaseModel):
    total_count: int
    normal_one_period_count: int
    normal_two_period_count: int
    normal_total_count: int
    normal_extra_count: int
    sexi_count: int
    leader_count: int
    head_count: int
    vice_count: int
    event_count: int
    gender_breakdown: dict[str, int] = Field(default_factory=dict)
    year_breakdown: dict[str, int] = Field(default_factory=dict)


class GroupResult(BaseModel):
    period: int
    group_number: int
    label: str
    is_international: bool
    mentors: list[AssignedMentor]
    summary: GroupSummary


class RequestOutcome(BaseModel):
    mentor_id: str
    mentor_name: str
    period: int
    requested_ids: list[str]
    matched_ids: list[str]
    satisfied: bool


class PreferredPeriodMiss(BaseModel):
    mentor_id: str
    mentor_name: str
    preferred_period: int
    assigned_period: int


class RepeatedGroupmateDetail(BaseModel):
    mentor_id: str
    mentor_name: str
    repeated_groupmate_count: int
    repeated_with: list[str] = Field(default_factory=list)


class QuotaDeviation(BaseModel):
    period: int
    group_number: int
    label: str
    is_international: bool
    target_normal_one_period_baseline: int
    actual_normal_one_period_count: int
    target_normal_two_period_baseline: int
    actual_normal_two_period_count: int
    target_extra_normal_count: int
    actual_extra_normal_count: int
    target_total_normal_count: int
    actual_total_normal_count: int
    extra_two_period_count: int


class RuleEvaluation(BaseModel):
    code: str
    title: str
    priority: int | None = None
    kind: RuleKind
    status: RuleStatus
    summary: str
    details: list[str] = Field(default_factory=list)


class DistributionPeriodSummary(BaseModel):
    period: int
    counts_by_group: list[int]
    min_count: int
    max_count: int
    average_count: float


class DistributionSeries(BaseModel):
    category: str
    value: str
    overall_min_count: int
    overall_max_count: int
    overall_range: int
    per_period: list[DistributionPeriodSummary] = Field(default_factory=list)


class ScoreComponent(BaseModel):
    key: str
    label: str
    category: str
    weight: int
    raw_value: int
    weighted_penalty: int


class ScoreBreakdown(BaseModel):
    components: list[ScoreComponent] = Field(default_factory=list)
    grouped_penalties: dict[str, int] = Field(default_factory=dict)
    total_penalty: int = 0


class SolveSummary(BaseModel):
    mentor_count: int
    group_count: int
    total_assignments: int
    international_group_count: int
    blocked_pair_count: int
    blocked_pair_violations: int
    one_period_assignment_violations: int
    two_period_assignment_violations: int
    leader_assignment_violations: int
    leader_role_violations: int
    leader_group_role_violations: int
    nonpreferred_international_repeat_violations: int
    event_absolute_violations: int
    exact_quota_group_count: int
    quota_deviation_group_count: int
    preferred_international_satisfied: int
    preferred_international_total: int
    nonpreferred_international_assignments: int
    requested_partner_satisfied: int
    requested_partner_total: int
    preferred_period_satisfied: int
    preferred_period_total: int
    repeated_groupmate_pair_count: int


class CompromiseReport(BaseModel):
    overview: list[str] = Field(default_factory=list)
    hard_constraint_statuses: list[RuleEvaluation] = Field(default_factory=list)
    soft_goal_statuses: list[RuleEvaluation] = Field(default_factory=list)
    compromises: list[str] = Field(default_factory=list)
    diagnostics: list[str] = Field(default_factory=list)
    quota_deviations: list[QuotaDeviation] = Field(default_factory=list)
    request_outcomes: list[RequestOutcome] = Field(default_factory=list)
    preferred_period_misses: list[PreferredPeriodMiss] = Field(default_factory=list)
    repeated_groupmates: list[RepeatedGroupmateDetail] = Field(default_factory=list)
    distributions: list[DistributionSeries] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)


class SolveResponse(BaseModel):
    status: SolveStatus
    objective_value: int | None = None
    warnings: list[ScenarioIssue] = Field(default_factory=list)
    errors: list[ScenarioIssue] = Field(default_factory=list)
    assignments: list[GroupResult] = Field(default_factory=list)
    summary: SolveSummary | None = None
    score: ScoreBreakdown | None = None
    report: CompromiseReport | None = None
    solver_stats: dict[str, Any] = Field(default_factory=dict)


class SavedProposalSummary(BaseModel):
    status: str
    objective_value: int | None = None
    group_count: int
    requested_partner_satisfied: int
    requested_partner_total: int
    preferred_period_satisfied: int
    preferred_period_total: int
    exact_quota_group_count: int
    total_group_count: int


class SavedProposalRecord(BaseModel):
    id: str = Field(min_length=1)
    name: str = Field(min_length=1)
    created_at: str = Field(min_length=1)
    scenario: ScenarioInput
    validation: ValidationResponse | None = None
    solution: SolveResponse
    summary: SavedProposalSummary


class WorkspaceState(BaseModel):
    scenario: ScenarioInput
    saved_proposals: list[SavedProposalRecord] = Field(default_factory=list)
