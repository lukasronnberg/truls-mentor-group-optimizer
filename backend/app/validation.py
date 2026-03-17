from __future__ import annotations

from .models import (
    IssueSeverity,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    ScenarioInput,
    ScenarioIssue,
    ValidationResponse,
    ValidationSummary,
)


def analyze_scenario(scenario: ScenarioInput) -> ValidationResponse:
    settings = scenario.settings
    mentors = scenario.mentors

    normal_one_supply = sum(
        1
        for mentor in mentors
        if mentor.category == MentorCategory.NORMAL
        and mentor.participation == ParticipationKind.ONE_PERIOD
    )
    normal_two_supply = sum(
        1
        for mentor in mentors
        if mentor.category == MentorCategory.NORMAL
        and mentor.participation == ParticipationKind.TWO_PERIOD
    )
    sexi_supply = sum(1 for mentor in mentors if mentor.category == MentorCategory.SEXI)
    leader_supply = sum(1 for mentor in mentors if mentor.category == MentorCategory.HOVDING)
    event_assignment_supply = sum(
        settings.period_count if mentor.participation == ParticipationKind.TWO_PERIOD else 1
        for mentor in mentors
        if mentor.category == MentorCategory.NORMAL and mentor.normal_subrole == NormalSubrole.EVENT
    )
    international_preference_count = sum(1 for mentor in mentors if mentor.prefers_international)
    international_hard_demand_by_period = {
        period: sum(
            1
            for mentor in mentors
            if mentor.prefers_international
            and (
                mentor.participation == ParticipationKind.TWO_PERIOD
                or mentor.preferred_period == period
            )
        )
        for period in range(1, settings.period_count + 1)
    }
    international_total_normal_capacity = (
        settings.regular_group_quota_one_period
        + settings.regular_group_quota_two_period
        + settings.international_extra_mentors
    )

    summary = ValidationSummary(
        mentor_count=len(mentors),
        blocked_pair_count=len(scenario.blocked_pairs),
        normal_one_period_supply=normal_one_supply,
        normal_one_period_target=settings.total_regular_normal_one_slots,
        normal_two_period_supply=normal_two_supply,
        normal_two_period_target=settings.ideal_distinct_normal_two_mentors,
        sexi_supply=sexi_supply,
        leader_supply=leader_supply,
        leader_target=settings.distinct_leader_target,
        event_assignment_supply=event_assignment_supply,
        event_ideal_capacity=settings.total_group_slots * settings.ideal_max_event_mentors_per_group,
        event_absolute_capacity=settings.total_group_slots * settings.absolute_max_event_mentors_per_group,
        international_preference_count=international_preference_count,
    )

    errors: list[ScenarioIssue] = []
    warnings: list[ScenarioIssue] = []

    if settings.groups_per_period != 10:
        warnings.append(
            ScenarioIssue(
                code="nonstandard_groups_per_period",
                severity=IssueSeverity.WARNING,
                message="This scenario does not use the domain-default 10 groups per period.",
                details=(
                    f"groups_per_period={settings.groups_per_period}. This is acceptable for testing, "
                    "but the real-world problem statement assumes 10."
                ),
            )
        )

    if normal_one_supply != settings.total_regular_normal_one_slots:
        relation = "fewer" if normal_one_supply < settings.total_regular_normal_one_slots else "more"
        warnings.append(
            ScenarioIssue(
                code="normal_one_supply_mismatch",
                severity=IssueSeverity.WARNING,
                message="Normal one-period supply does not match the exact base quota target.",
                details=(
                    f"There are {normal_one_supply} normal one-period mentors, which is {relation} than "
                    f"the ideal target of {settings.total_regular_normal_one_slots}."
                ),
            )
        )

    if normal_two_supply != settings.ideal_distinct_normal_two_mentors:
        relation = "fewer" if normal_two_supply < settings.ideal_distinct_normal_two_mentors else "more"
        warnings.append(
            ScenarioIssue(
                code="normal_two_supply_mismatch",
                severity=IssueSeverity.WARNING,
                message="Normal two-period supply does not match the ideal quota target.",
                details=(
                    f"There are {normal_two_supply} normal two-period mentors, which is {relation} than "
                    f"the ideal target of {settings.ideal_distinct_normal_two_mentors}. "
                    "International extra slots may require compromise."
                ),
            )
        )

    if leader_supply != settings.distinct_leader_target:
        errors.append(
            ScenarioIssue(
                code="leader_supply_mismatch",
                severity=IssueSeverity.ERROR,
                message="Leader count does not match the exact domain requirement.",
                details=(
                    f"There are {leader_supply} hovding mentors, but {settings.distinct_leader_target} "
                    "are required so every group gets one head and one vice in both periods."
                ),
            )
        )

    invalid_leaders = [
        mentor.id
        for mentor in mentors
        if mentor.category == MentorCategory.HOVDING
        and mentor.participation != ParticipationKind.TWO_PERIOD
    ]
    if invalid_leaders:
        errors.append(
            ScenarioIssue(
                code="leader_participation_invalid",
                severity=IssueSeverity.ERROR,
                message="All leaders must participate in both periods.",
                details=", ".join(invalid_leaders[:10]),
            )
        )

    if event_assignment_supply > summary.event_absolute_capacity:
        errors.append(
            ScenarioIssue(
                code="event_capacity_impossible",
                severity=IssueSeverity.ERROR,
                message="Event mentor assignments exceed the hard maximum capacity.",
                details=(
                    f"Event mentors require {event_assignment_supply} assignment slots, but the hard limit "
                    f"is {summary.event_absolute_capacity} across all group-periods."
                ),
            )
        )
    elif event_assignment_supply > summary.event_ideal_capacity:
        warnings.append(
            ScenarioIssue(
                code="event_capacity_tight",
                severity=IssueSeverity.WARNING,
                message="Event mentor assignments exceed the ideal one-per-group target.",
                details=(
                    f"Event mentors require {event_assignment_supply} assignment slots, above the ideal "
                    f"capacity of {summary.event_ideal_capacity}. Some groups will likely receive two "
                    "event mentors."
                ),
            )
        )

    if settings.groups_per_period == 1:
        mentor_lookup = {mentor.id: mentor for mentor in mentors}
        impossible_pairs = [
            blocked_pair.normalized
            for blocked_pair in scenario.blocked_pairs
            if mentor_lookup[blocked_pair.mentor_a].participation == ParticipationKind.TWO_PERIOD
            and mentor_lookup[blocked_pair.mentor_b].participation == ParticipationKind.TWO_PERIOD
        ]
        if impossible_pairs:
            pair_list = ", ".join(f"{left}/{right}" for left, right in impossible_pairs[:5])
            errors.append(
                ScenarioIssue(
                    code="blocked_pair_impossible_single_group",
                    severity=IssueSeverity.ERROR,
                    message="A blocked pair makes the scenario impossible with only one group per period.",
                    details=(
                        f"Two-period mentors in blocked pair(s) {pair_list} would be forced into the only "
                        "group in both periods."
                    ),
                )
            )

    if not international_preference_count:
        warnings.append(
            ScenarioIssue(
                code="no_international_preferences",
                severity=IssueSeverity.WARNING,
                message="No normal mentors currently have the international subrole.",
                details="International-group prioritization will be driven only by other objectives.",
            )
        )
    else:
        for period, demand in international_hard_demand_by_period.items():
            if demand > international_total_normal_capacity:
                errors.append(
                    ScenarioIssue(
                        code="international_hard_assignment_impossible",
                        severity=IssueSeverity.ERROR,
                        message="International hard assignments exceed the international-group capacity.",
                        details=(
                            f"Period {period} has {demand} mentors marked international, but the international "
                            f"group can only hold {international_total_normal_capacity} normal mentors."
                        ),
                    )
                )

    if not any(
        mentor.category == MentorCategory.SEXI and mentor.participation == ParticipationKind.TWO_PERIOD
        for mentor in mentors
    ):
        warnings.append(
            ScenarioIssue(
                code="no_two_period_sexi",
                severity=IssueSeverity.WARNING,
                message="No sexi mentors participate in both periods.",
                details="Sexi distribution can still work, but the additive pool is entirely period-specific.",
            )
        )

    return ValidationResponse(ok=not errors, errors=errors, warnings=warnings, summary=summary)
