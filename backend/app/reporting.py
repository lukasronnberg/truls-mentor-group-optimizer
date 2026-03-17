from __future__ import annotations

from .models import (
    CompromiseReport,
    DistributionSeries,
    PreferredPeriodMiss,
    QuotaDeviation,
    RepeatedGroupmateDetail,
    RequestOutcome,
    RuleEvaluation,
    RuleKind,
    RuleStatus,
    ScenarioInput,
    ScoreBreakdown,
    SolveSummary,
    ValidationResponse,
)


def build_compromise_report(
    scenario: ScenarioInput,
    validation: ValidationResponse,
    summary: SolveSummary,
    score: ScoreBreakdown,
    quota_deviations: list[QuotaDeviation],
    request_outcomes: list[RequestOutcome],
    preferred_period_misses: list[PreferredPeriodMiss],
    repeated_groupmates: list[RepeatedGroupmateDetail],
    distributions: list[DistributionSeries],
    used_strict_quotas: bool,
    used_sexi_guard: bool,
) -> CompromiseReport:
    requests_by_period = _request_period_summary(request_outcomes, scenario.settings.period_count)
    sexi_distribution = _distribution_lookup(distributions).get(("sexi", "sexi mentors"))
    sexi_target_met = _distribution_within_target(sexi_distribution)

    hard_constraint_statuses = [
        RuleEvaluation(
            code="blocked_pairs",
            title="Blocked pairs",
            priority=1,
            kind=RuleKind.HARD,
            status=RuleStatus.SATISFIED if summary.blocked_pair_violations == 0 else RuleStatus.VIOLATED,
            summary=(
                f"{summary.blocked_pair_count - summary.blocked_pair_violations} of "
                f"{summary.blocked_pair_count} blocked-pair checks were respected."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="assignment_cardinality",
            title="Participation assignment counts",
            kind=RuleKind.HARD,
            status=(
                RuleStatus.SATISFIED
                if summary.one_period_assignment_violations == 0
                and summary.two_period_assignment_violations == 0
                else RuleStatus.VIOLATED
            ),
            summary=(
                "Each one-period mentor was assigned once and each two-period mentor was assigned once per period."
                if summary.one_period_assignment_violations == 0
                and summary.two_period_assignment_violations == 0
                else "At least one participation-count rule was violated."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="leader_structure",
            title="Leader head/vice structure",
            kind=RuleKind.HARD,
            status=(
                RuleStatus.SATISFIED
                if summary.leader_assignment_violations == 0
                and summary.leader_role_violations == 0
                and summary.leader_group_role_violations == 0
                else RuleStatus.VIOLATED
            ),
            summary=(
                "Every group received exactly one head and one vice, and each leader was head once and vice once."
                if summary.leader_assignment_violations == 0
                and summary.leader_role_violations == 0
                and summary.leader_group_role_violations == 0
                else "At least one leader assignment or head/vice rule was violated."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="international_hard_assignments",
            title="International hard assignments",
            priority=3,
            kind=RuleKind.HARD,
            status=(
                RuleStatus.SATISFIED
                if summary.preferred_international_satisfied == summary.preferred_international_total
                else RuleStatus.VIOLATED
            ),
            summary=(
                f"{summary.preferred_international_satisfied} of {summary.preferred_international_total} mentors marked for international were assigned there in every participated period."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="event_absolute_max",
            title="Event mentor hard maximum",
            kind=RuleKind.HARD,
            status=RuleStatus.SATISFIED if summary.event_absolute_violations == 0 else RuleStatus.VIOLATED,
            summary=(
                "No group exceeded the absolute maximum of two event mentors."
                if summary.event_absolute_violations == 0
                else "At least one group exceeded the hard event-mentor maximum."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="nonpreferred_international_limit",
            title="Non-international cap",
            kind=RuleKind.HARD,
            status=(
                RuleStatus.SATISFIED
                if summary.nonpreferred_international_repeat_violations == 0
                else RuleStatus.VIOLATED
            ),
            summary=(
                "No non-international mentor was assigned to an international group in both periods."
                if summary.nonpreferred_international_repeat_violations == 0
                else "At least one non-international mentor was assigned to international in both periods."
            ),
            details=[],
        ),
    ]

    request_unsatisfied_count = sum(1 for outcome in request_outcomes if not outcome.satisfied)
    soft_goal_statuses = [
        RuleEvaluation(
            code="normal_quotas",
            title="Normal-pool quotas",
            priority=2,
            kind=RuleKind.SOFT,
            status=(
                RuleStatus.SATISFIED
                if summary.quota_deviation_group_count == 0
                else RuleStatus.PARTIALLY_SATISFIED
            ),
            summary=(
                f"Exact normal-pool quota shape was achieved in {summary.exact_quota_group_count} of "
                f"{summary.group_count} group-periods."
            ),
            details=[
                "Strict quota mode was feasible and used."
                if used_strict_quotas
                else "Strict quota mode was infeasible, so quota deviations were relaxed and penalized."
            ],
        ),
        RuleEvaluation(
            code="nonpreferred_international_usage",
            title="Non-requested international placements",
            priority=3,
            kind=RuleKind.SOFT,
            status=(
                RuleStatus.SATISFIED
                if summary.nonpreferred_international_assignments == 0
                else RuleStatus.PARTIALLY_SATISFIED
            ),
            summary=(
                f"{summary.nonpreferred_international_assignments} non-international mentors were placed in an international group."
            ),
            details=[
                "Mentors explicitly marked international are now treated as a hard assignment, not a preference."
            ],
        ),
        RuleEvaluation(
            code="requested_partners",
            title="Requested partners per participated period",
            priority=4,
            kind=RuleKind.SOFT,
            status=(
                RuleStatus.SATISFIED
                if request_unsatisfied_count == 0
                else RuleStatus.PARTIALLY_SATISFIED
            ),
            summary=(
                f"{summary.requested_partner_satisfied} of {summary.requested_partner_total} mentor-period "
                "request checks were satisfied."
            ),
            details=[
                f"Period {period}: {period_summary['satisfied']} of {period_summary['total']} mentors with wishes got at least one requested partner."
                for period, period_summary in requests_by_period.items()
            ],
        ),
        RuleEvaluation(
            code="preferred_periods",
            title="Preferred periods for one-period normal mentors",
            kind=RuleKind.SOFT,
            status=(
                RuleStatus.SATISFIED
                if summary.preferred_period_satisfied == summary.preferred_period_total
                else RuleStatus.PARTIALLY_SATISFIED
            ),
            summary=(
                f"{summary.preferred_period_satisfied} of {summary.preferred_period_total} one-period normal mentors "
                "received their preferred period."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="repeated_groupmates",
            title="Repeated normal two-period groupmates",
            kind=RuleKind.SOFT,
            status=(
                RuleStatus.SATISFIED
                if summary.repeated_groupmate_pair_count == 0
                else RuleStatus.PARTIALLY_SATISFIED
            ),
            summary=(
                f"{summary.repeated_groupmate_pair_count} repeated normal two-period pairings remained across periods."
            ),
            details=[],
        ),
        RuleEvaluation(
            code="distribution_balance",
            title="Distribution balance",
            priority=5,
            kind=RuleKind.SOFT,
            status=_distribution_status(distributions),
            summary="Sexi mentors, event mentors, gender, and year were balanced as evenly as possible.",
            details=[
                (
                    f"Sexi spread target was enforced directly (max 3 per group and max spread 2)."
                    if used_sexi_guard
                    else "Sexi spread target had to relax to objective-only mode, but TRULS still minimized max load and spread aggressively."
                ),
                *(
                    [
                        f"Sexi distribution: period {period.period} min {period.min_count}, max {period.max_count}, counts {period.counts_by_group}."
                        for period in sexi_distribution.per_period
                    ]
                    if sexi_distribution
                    else []
                ),
                (
                    "Sexi distribution stayed within the target band of max 3 per group and max spread 2."
                    if sexi_target_met
                    else "Sexi distribution exceeded the target band and should be reviewed."
                )
                if sexi_distribution
                else "No sexi mentors were present in the scenario.",
            ],
        ),
    ]

    overview = [
        (
            "All hard constraints were satisfied."
            if all(rule.status == RuleStatus.SATISFIED for rule in hard_constraint_statuses)
            else "At least one hard constraint failed, which indicates a serious solver issue."
        ),
        (
            "Strict normal-pool quotas were enforced directly."
            if used_strict_quotas
            else "Strict normal-pool quotas were not all feasible, so the solver returned the best relaxed-feasible compromise."
        ),
        f"Leader hard-rule violations: assignments={summary.leader_assignment_violations}, role-balance={summary.leader_role_violations}, group-role={summary.leader_group_role_violations}.",
        f"International hard assignments satisfied: {summary.preferred_international_satisfied}/{summary.preferred_international_total}.",
        f"Requested partner satisfaction: {summary.requested_partner_satisfied}/{summary.requested_partner_total}.",
        *[
            f"Requested partner satisfaction in period {period}: {period_summary['satisfied']}/{period_summary['total']}."
            for period, period_summary in requests_by_period.items()
        ],
        f"Preferred-period satisfaction: {summary.preferred_period_satisfied}/{summary.preferred_period_total}.",
        f"Repeated normal two-period pairs: {summary.repeated_groupmate_pair_count}.",
        *(
            [
                f"Sexi distribution in period {period.period}: min {period.min_count}, max {period.max_count}, counts {period.counts_by_group}."
                for period in sexi_distribution.per_period
            ]
            if sexi_distribution
            else []
        ),
    ]

    compromises: list[str] = []
    for deviation in quota_deviations[:10]:
        compromises.append(
            f"{deviation.label}: normal one-period {deviation.actual_normal_one_period_count} "
            f"(baseline {deviation.target_normal_one_period_baseline}), normal two-period "
            f"{deviation.actual_normal_two_period_count} (baseline {deviation.target_normal_two_period_baseline}), "
            f"extra normal mentors {deviation.actual_extra_normal_count} of {deviation.target_extra_normal_count}."
        )

    for miss in preferred_period_misses[:10]:
        compromises.append(
            f"{miss.mentor_name} preferred period {miss.preferred_period} but was assigned to period {miss.assigned_period}."
        )

    for outcome in [item for item in request_outcomes if not item.satisfied][:10]:
        compromises.append(
            f"{outcome.mentor_name} had no requested partner in period {outcome.period}."
        )

    for repeated in [item for item in repeated_groupmates if item.repeated_groupmate_count > 0][:10]:
        compromises.append(
            f"{repeated.mentor_name} repeated {repeated.repeated_groupmate_count} groupmate(s): {', '.join(repeated.repeated_with)}."
        )

    diagnostics = [
        f"Normal one-period supply: {validation.summary.normal_one_period_supply}/{validation.summary.normal_one_period_target}.",
        f"Normal two-period supply: {validation.summary.normal_two_period_supply}/{validation.summary.normal_two_period_target}.",
        f"Leader supply: {validation.summary.leader_supply}/{validation.summary.leader_target}.",
        f"Event assignment demand: {validation.summary.event_assignment_supply}/{validation.summary.event_absolute_capacity} hard capacity.",
        *[
            issue.message if not issue.details else f"{issue.message} {issue.details}"
            for issue in validation.warnings
        ],
        *[
            f"{component.label}: raw={component.raw_value}, weight={component.weight}, penalty={component.weighted_penalty}."
            for component in score.components
            if component.raw_value
        ],
    ]

    metadata = {
        "score_grouped_penalties": score.grouped_penalties,
        "validation_warning_count": len(validation.warnings),
        "validation_error_count": len(validation.errors),
        "sexi_target": {
            "max_per_group": 3,
            "max_spread": 2,
            "guarded_mode_used": used_sexi_guard,
            "within_target": sexi_target_met,
        },
        "sexi_distribution": (
            {
                f"period_{period.period}": {
                    "counts_by_group": period.counts_by_group,
                    "min": period.min_count,
                    "max": period.max_count,
                    "range": period.max_count - period.min_count,
                }
                for period in sexi_distribution.per_period
            }
            if sexi_distribution
            else {}
        ),
        "requested_partner_summary": {
            f"period_{period}": period_summary for period, period_summary in requests_by_period.items()
        },
    }

    return CompromiseReport(
        overview=overview,
        hard_constraint_statuses=hard_constraint_statuses,
        soft_goal_statuses=soft_goal_statuses,
        compromises=compromises,
        diagnostics=diagnostics,
        quota_deviations=quota_deviations,
        request_outcomes=request_outcomes,
        preferred_period_misses=preferred_period_misses,
        repeated_groupmates=repeated_groupmates,
        distributions=distributions,
        metadata=metadata,
    )


def build_infeasible_report(validation: ValidationResponse) -> CompromiseReport:
    return CompromiseReport(
        overview=["The scenario is infeasible before solving because validation found fatal issues."],
        diagnostics=[
            issue.message if not issue.details else f"{issue.message} {issue.details}"
            for issue in [*validation.errors, *validation.warnings]
        ],
        metadata={
            "validation_warning_count": len(validation.warnings),
            "validation_error_count": len(validation.errors),
        },
    )


def _distribution_status(distributions: list[DistributionSeries]) -> RuleStatus:
    if not distributions:
        return RuleStatus.NOT_APPLICABLE
    return (
        RuleStatus.SATISFIED
        if all(series.overall_range <= 1 for series in distributions)
        else RuleStatus.PARTIALLY_SATISFIED
    )


def _distribution_lookup(
    distributions: list[DistributionSeries],
) -> dict[tuple[str, str], DistributionSeries]:
    return {(series.category, series.value): series for series in distributions}


def _distribution_within_target(series: DistributionSeries | None) -> bool:
    if series is None:
        return True
    return all(period.max_count <= 3 and (period.max_count - period.min_count) <= 2 for period in series.per_period)


def _request_period_summary(
    request_outcomes: list[RequestOutcome],
    period_count: int,
) -> dict[int, dict[str, object]]:
    grouped: dict[int, dict[str, object]] = {}
    for period in range(1, period_count + 1):
        period_outcomes = [outcome for outcome in request_outcomes if outcome.period == period]
        grouped[period] = {
            "total": len(period_outcomes),
            "satisfied": sum(1 for outcome in period_outcomes if outcome.satisfied),
            "missing_names": [outcome.mentor_name for outcome in period_outcomes if not outcome.satisfied],
        }
    return grouped
