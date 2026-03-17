from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from itertools import combinations

from ortools.sat.python import cp_model

from .models import (
    AssignedMentor,
    DistributionPeriodSummary,
    DistributionSeries,
    GroupResult,
    GroupSummary,
    IssueSeverity,
    LeaderRole,
    Mentor,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    PreferredPeriodMiss,
    QuotaDeviation,
    RepeatedGroupmateDetail,
    RequestOutcome,
    ScenarioInput,
    ScenarioIssue,
    SolveResponse,
    SolveStatus,
    SolveSummary,
)
from .reporting import build_compromise_report, build_infeasible_report
from .scoring import ObjectiveTracker
from .validation import analyze_scenario


@dataclass
class ModelArtifacts:
    assignment_vars: dict[tuple[int, int, int], cp_model.IntVar]
    leader_role_vars: dict[tuple[int, int, int, str], cp_model.IntVar]
    objective_tracker: ObjectiveTracker
    international_group_by_period: dict[int, int]


class PairCache:
    def __init__(
        self,
        model: cp_model.CpModel,
        assignment_vars: dict[tuple[int, int, int], cp_model.IntVar],
        groups_per_period: int,
    ) -> None:
        self.model = model
        self.assignment_vars = assignment_vars
        self.groups_per_period = groups_per_period
        self.same_group_vars: dict[tuple[int, int, int, int], cp_model.IntVar] = {}
        self.same_period_vars: dict[tuple[int, int, int], cp_model.IntVar] = {}

    def same_group(self, mentor_a: int, mentor_b: int, period: int, group: int) -> cp_model.IntVar:
        left, right = sorted((mentor_a, mentor_b))
        key = (left, right, period, group)
        if key not in self.same_group_vars:
            same_group_var = self.model.NewBoolVar(f"same_group_{left}_{right}_p{period}_g{group}")
            self.model.Add(same_group_var <= self.assignment_vars[(left, period, group)])
            self.model.Add(same_group_var <= self.assignment_vars[(right, period, group)])
            self.model.Add(
                same_group_var
                >= self.assignment_vars[(left, period, group)]
                + self.assignment_vars[(right, period, group)]
                - 1
            )
            self.same_group_vars[key] = same_group_var
        return self.same_group_vars[key]

    def same_period(self, mentor_a: int, mentor_b: int, period: int) -> cp_model.IntVar:
        left, right = sorted((mentor_a, mentor_b))
        key = (left, right, period)
        if key not in self.same_period_vars:
            same_period_var = self.model.NewBoolVar(f"same_period_{left}_{right}_p{period}")
            per_group = [
                self.same_group(left, right, period, group)
                for group in range(self.groups_per_period)
            ]
            self.model.Add(same_period_var == sum(per_group))
            self.same_period_vars[key] = same_period_var
        return self.same_period_vars[key]


def solve_scenario(scenario: ScenarioInput) -> SolveResponse:
    validation = analyze_scenario(scenario)
    if validation.errors:
        return SolveResponse(
            status=SolveStatus.INFEASIBLE,
            warnings=validation.warnings,
            errors=validation.errors,
            assignments=[],
            report=build_infeasible_report(validation),
            solver_stats={"status_name": "validation_infeasible", "quota_mode": "not_run"},
        )

    attempts: list[tuple[bool, bool]] = []
    if scenario.settings.enforce_strict_quotas_when_feasible:
        attempts.extend([(True, True), (True, False)])
    attempts.extend([(False, True), (False, False)])

    seen_attempts: set[tuple[bool, bool]] = set()
    for strict_quotas, enforce_sexi_guard in attempts:
        if (strict_quotas, enforce_sexi_guard) in seen_attempts:
            continue
        seen_attempts.add((strict_quotas, enforce_sexi_guard))
        response = _solve_with_mode(
            scenario,
            validation,
            strict_quotas=strict_quotas,
            enforce_sexi_guard=enforce_sexi_guard,
        )
        if response is not None:
            return response

    infeasible_error = ScenarioIssue(
        code="solver_infeasible",
        severity=IssueSeverity.ERROR,
        message="The CP-SAT model could not find a feasible solution.",
        details="This remained infeasible even after relaxing quota constraints.",
    )
    errors = [*validation.errors, infeasible_error]
    validation.errors = errors
    return SolveResponse(
        status=SolveStatus.INFEASIBLE,
        warnings=validation.warnings,
        errors=errors,
        assignments=[],
        report=build_infeasible_report(validation),
        solver_stats={"status_name": "INFEASIBLE", "quota_mode": "relaxed"},
    )


def _solve_with_mode(
    scenario: ScenarioInput,
    validation,
    strict_quotas: bool,
    enforce_sexi_guard: bool,
) -> SolveResponse | None:
    mentors = scenario.mentors
    settings = scenario.settings
    periods = list(range(settings.period_count))
    groups = list(range(settings.groups_per_period))
    mentor_index = {mentor.id: index for index, mentor in enumerate(mentors)}
    international_group_by_period = {
        period - 1: group_number - 1
        for period, group_number in settings.international_group_numbers.items()
    }

    model = cp_model.CpModel()
    assignment_vars: dict[tuple[int, int, int], cp_model.IntVar] = {
        (mentor_idx, period, group): model.NewBoolVar(f"x_{mentor_idx}_p{period}_g{group}")
        for mentor_idx in range(len(mentors))
        for period in periods
        for group in groups
    }
    leader_role_vars: dict[tuple[int, int, int, str], cp_model.IntVar] = {}
    pair_cache = PairCache(model, assignment_vars, settings.groups_per_period)
    objective_tracker = ObjectiveTracker(scenario.weights)
    sexi_count_vars: dict[tuple[int, int], cp_model.IntVar] = {}

    one_period_mentors = [
        index for index, mentor in enumerate(mentors) if mentor.participation == ParticipationKind.ONE_PERIOD
    ]
    two_period_mentors = [
        index for index, mentor in enumerate(mentors) if mentor.participation == ParticipationKind.TWO_PERIOD
    ]
    normal_one_period_mentors = [
        index
        for index, mentor in enumerate(mentors)
        if mentor.category == MentorCategory.NORMAL
        and mentor.participation == ParticipationKind.ONE_PERIOD
    ]
    normal_two_period_mentors = [
        index
        for index, mentor in enumerate(mentors)
        if mentor.category == MentorCategory.NORMAL
        and mentor.participation == ParticipationKind.TWO_PERIOD
    ]
    sexi_mentors = [
        index for index, mentor in enumerate(mentors) if mentor.category == MentorCategory.SEXI
    ]
    leader_mentors = [
        index for index, mentor in enumerate(mentors) if mentor.category == MentorCategory.HOVDING
    ]
    event_mentors = [
        index
        for index, mentor in enumerate(mentors)
        if mentor.category == MentorCategory.NORMAL and mentor.normal_subrole == NormalSubrole.EVENT
    ]
    for mentor_idx in two_period_mentors:
        for period in periods:
            model.Add(sum(assignment_vars[(mentor_idx, period, group)] for group in groups) == 1)

    for mentor_idx in one_period_mentors:
        for period in periods:
            model.Add(sum(assignment_vars[(mentor_idx, period, group)] for group in groups) <= 1)
        model.Add(
            sum(
                assignment_vars[(mentor_idx, period, group)]
                for period in periods
                for group in groups
            )
            == 1
        )

    for mentor_idx in leader_mentors:
        for period in periods:
            head_vars = []
            vice_vars = []
            for group in groups:
                head_var = model.NewBoolVar(f"leader_head_{mentor_idx}_p{period}_g{group}")
                vice_var = model.NewBoolVar(f"leader_vice_{mentor_idx}_p{period}_g{group}")
                leader_role_vars[(mentor_idx, period, group, LeaderRole.HEAD.value)] = head_var
                leader_role_vars[(mentor_idx, period, group, LeaderRole.VICE.value)] = vice_var
                head_vars.append(head_var)
                vice_vars.append(vice_var)
                model.Add(assignment_vars[(mentor_idx, period, group)] == head_var + vice_var)

            model.Add(sum(head_vars) + sum(vice_vars) == 1)

        model.Add(
            sum(
                leader_role_vars[(mentor_idx, period, group, LeaderRole.HEAD.value)]
                for period in periods
                for group in groups
            )
            == 1
        )
        model.Add(
            sum(
                leader_role_vars[(mentor_idx, period, group, LeaderRole.VICE.value)]
                for period in periods
                for group in groups
            )
            == 1
        )

    for blocked_pair in scenario.blocked_pairs:
        left = mentor_index[blocked_pair.mentor_a]
        right = mentor_index[blocked_pair.mentor_b]
        for period in periods:
            for group in groups:
                model.Add(
                    assignment_vars[(left, period, group)] + assignment_vars[(right, period, group)] <= 1
                )

    for mentor_idx, mentor in enumerate(mentors):
        if not mentor.prefers_international:
            continue
        if mentor.participation == ParticipationKind.TWO_PERIOD:
            for period in periods:
                model.Add(
                    assignment_vars[(mentor_idx, period, international_group_by_period[period])] == 1
                )
        else:
            preferred_period = (mentor.preferred_period or 1) - 1
            for period in periods:
                if period == preferred_period:
                    model.Add(
                        assignment_vars[(mentor_idx, period, international_group_by_period[period])] == 1
                    )
                else:
                    for group in groups:
                        model.Add(assignment_vars[(mentor_idx, period, group)] == 0)

    for mentor_idx, mentor in enumerate(mentors):
        if mentor.prefers_international:
            continue
        model.Add(
            sum(
                assignment_vars[(mentor_idx, period, international_group_by_period[period])]
                for period in periods
            )
            <= 1
        )

    for period in periods:
        for group in groups:
            event_count = sum(assignment_vars[(mentor_idx, period, group)] for mentor_idx in event_mentors)
            model.Add(event_count <= settings.absolute_max_event_mentors_per_group)

            head_count = sum(
                leader_role_vars[(mentor_idx, period, group, LeaderRole.HEAD.value)]
                for mentor_idx in leader_mentors
            )
            vice_count = sum(
                leader_role_vars[(mentor_idx, period, group, LeaderRole.VICE.value)]
                for mentor_idx in leader_mentors
            )
            model.Add(head_count == 1)
            model.Add(vice_count == 1)

    def count_var(name: str, mentor_indices: list[int], period: int, group: int) -> cp_model.IntVar:
        variable = model.NewIntVar(0, len(mentor_indices), f"{name}_p{period}_g{group}")
        model.Add(variable == sum(assignment_vars[(mentor_idx, period, group)] for mentor_idx in mentor_indices))
        return variable

    for period in periods:
        for group in groups:
            normal_one_count = count_var("normal_one", normal_one_period_mentors, period, group)
            normal_two_count = count_var("normal_two", normal_two_period_mentors, period, group)
            normal_total_count = model.NewIntVar(
                0,
                len(normal_one_period_mentors) + len(normal_two_period_mentors),
                f"normal_total_p{period}_g{group}",
            )
            model.Add(normal_total_count == normal_one_count + normal_two_count)

            event_count = count_var("event", event_mentors, period, group)
            sexi_count = count_var("sexi", sexi_mentors, period, group)
            leader_count = count_var("leader", leader_mentors, period, group)
            sexi_count_vars[(period, group)] = sexi_count
            model.Add(leader_count == 2)

            is_international = group == international_group_by_period[period]
            if is_international:
                _apply_international_quota_constraints(
                    model=model,
                    objective_tracker=objective_tracker,
                    strict_quotas=strict_quotas,
                    normal_one_count=normal_one_count,
                    normal_two_count=normal_two_count,
                    normal_total_count=normal_total_count,
                    period=period,
                    group=group,
                    settings=settings,
                )
            else:
                _apply_regular_quota_constraints(
                    model=model,
                    objective_tracker=objective_tracker,
                    strict_quotas=strict_quotas,
                    normal_one_count=normal_one_count,
                    normal_two_count=normal_two_count,
                    period=period,
                    group=group,
                    settings=settings,
                )

            second_event_penalty = model.NewIntVar(
                0,
                settings.absolute_max_event_mentors_per_group,
                f"event_second_penalty_p{period}_g{group}",
            )
            model.Add(second_event_penalty >= event_count - settings.ideal_max_event_mentors_per_group)
            objective_tracker.add("event_second_mentor", second_event_penalty)

    for mentor_idx, mentor in enumerate(mentors):
        international_assignments = [
            assignment_vars[(mentor_idx, period, international_group_by_period[period])]
            for period in periods
        ]
        if not mentor.prefers_international:
            for assignment in international_assignments:
                objective_tracker.add("nonpreferred_international", assignment)

    for mentor_idx, mentor in enumerate(mentors):
        if not mentor.requested_with:
            continue
        for period in periods:
            participation = model.NewBoolVar(f"participation_{mentor_idx}_p{period}")
            model.Add(participation == sum(assignment_vars[(mentor_idx, period, group)] for group in groups))
            same_requested_vars = [
                pair_cache.same_period(mentor_idx, mentor_index[requested_id], period)
                for requested_id in mentor.requested_with
            ]
            met_request = model.NewBoolVar(f"met_request_{mentor_idx}_p{period}")
            model.AddMaxEquality(met_request, same_requested_vars)
            miss_request = model.NewBoolVar(f"miss_request_{mentor_idx}_p{period}")
            model.Add(miss_request >= participation - met_request)
            model.Add(miss_request <= participation)
            model.Add(miss_request <= 1 - met_request)
            objective_tracker.add("request_missing", miss_request)

    for mentor_idx in normal_one_period_mentors:
        mentor = mentors[mentor_idx]
        if mentor.preferred_period is None:
            continue
        assigned_in_preferred_period = model.NewBoolVar(f"preferred_period_hit_{mentor_idx}")
        model.Add(
            assigned_in_preferred_period
            == sum(assignment_vars[(mentor_idx, mentor.preferred_period - 1, group)] for group in groups)
        )
        miss_preferred_period = model.NewBoolVar(f"preferred_period_miss_{mentor_idx}")
        model.Add(miss_preferred_period + assigned_in_preferred_period == 1)
        objective_tracker.add("preferred_period_miss", miss_preferred_period)

    repeated_pair_vars: dict[tuple[int, int], cp_model.IntVar] = {}
    repeated_pairs_by_mentor: dict[int, list[cp_model.IntVar]] = defaultdict(list)
    for left, right in combinations(normal_two_period_mentors, 2):
        same_period_one = pair_cache.same_period(left, right, 0)
        same_period_two = pair_cache.same_period(left, right, 1)
        repeated_pair = model.NewBoolVar(f"repeat_pair_{left}_{right}")
        model.Add(repeated_pair <= same_period_one)
        model.Add(repeated_pair <= same_period_two)
        model.Add(repeated_pair >= same_period_one + same_period_two - 1)
        repeated_pair_vars[(left, right)] = repeated_pair
        repeated_pairs_by_mentor[left].append(repeated_pair)
        repeated_pairs_by_mentor[right].append(repeated_pair)

    for mentor_idx in normal_two_period_mentors:
        repeated_count = model.NewIntVar(
            0,
            len(repeated_pairs_by_mentor.get(mentor_idx, [])),
            f"repeat_count_{mentor_idx}",
        )
        model.Add(repeated_count == sum(repeated_pairs_by_mentor.get(mentor_idx, [])))
        repeated_excess = model.NewIntVar(
            0,
            max(0, len(repeated_pairs_by_mentor.get(mentor_idx, [])) - 1),
            f"repeat_excess_{mentor_idx}",
        )
        model.Add(repeated_excess >= repeated_count - 1)
        objective_tracker.add("repeated_groupmates", repeated_excess)

    _add_strong_distribution_penalty(
        model=model,
        objective_tracker=objective_tracker,
        key="sexi_evenness",
        periods=periods,
        groups=groups,
        count_vars=sexi_count_vars,
        upper_bound=len(sexi_mentors),
        label="sexi",
        hard_max_spread=2 if enforce_sexi_guard else None,
        hard_max_count=3 if enforce_sexi_guard else None,
    )
    _add_range_penalty(
        model=model,
        objective_tracker=objective_tracker,
        key="event_evenness",
        periods=periods,
        groups=groups,
        assignment_vars=assignment_vars,
        mentor_indices=event_mentors,
        label="event",
    )
    for key, selector, label_prefix in (
        ("balance_gender", lambda mentor: mentor.gender, "gender"),
        ("balance_year", lambda mentor: mentor.year, "year"),
    ):
        values = sorted({selector(mentor) for mentor in mentors})
        for value in values:
            relevant_indices = [index for index, mentor in enumerate(mentors) if selector(mentor) == value]
            _add_range_penalty(
                model=model,
                objective_tracker=objective_tracker,
                key=key,
                periods=periods,
                groups=groups,
                assignment_vars=assignment_vars,
                mentor_indices=relevant_indices,
                label=f"{label_prefix}_{value}",
            )

    model.Minimize(objective_tracker.objective_expression())

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = (
        settings.max_solver_time_seconds
        if not strict_quotas
        else min(settings.max_solver_time_seconds, max(5, settings.max_solver_time_seconds // 2))
    )
    solver.parameters.num_search_workers = 8

    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    artifacts = ModelArtifacts(
        assignment_vars=assignment_vars,
        leader_role_vars=leader_role_vars,
        objective_tracker=objective_tracker,
        international_group_by_period=international_group_by_period,
    )
    assignments = _build_group_results(
        mentors=mentors,
        periods=periods,
        groups=groups,
        international_group_by_period=international_group_by_period,
        assignment_vars=assignment_vars,
        leader_role_vars=leader_role_vars,
        solver=solver,
    )
    score = objective_tracker.build_breakdown(solver)
    request_outcomes = _build_request_outcomes(mentors, assignments, periods)
    preferred_period_misses = _build_preferred_period_misses(mentors, assignments)
    repeated_groupmates = _build_repeated_groupmates(mentors, assignments)
    quota_deviations = _build_quota_deviations(scenario, assignments)
    distributions = _build_distribution_series(assignments)
    summary = _build_solve_summary(
        scenario=scenario,
        assignments=assignments,
        quota_deviations=quota_deviations,
        request_outcomes=request_outcomes,
        preferred_period_misses=preferred_period_misses,
        repeated_groupmates=repeated_groupmates,
        international_group_by_period=artifacts.international_group_by_period,
    )
    report = build_compromise_report(
        scenario=scenario,
        validation=validation,
        summary=summary,
        score=score,
        quota_deviations=quota_deviations,
        request_outcomes=request_outcomes,
        preferred_period_misses=preferred_period_misses,
        repeated_groupmates=repeated_groupmates,
        distributions=distributions,
        used_strict_quotas=strict_quotas,
        used_sexi_guard=enforce_sexi_guard,
    )
    return SolveResponse(
        status=SolveStatus.OPTIMAL if status == cp_model.OPTIMAL else SolveStatus.FEASIBLE,
        objective_value=int(solver.ObjectiveValue()),
        warnings=validation.warnings,
        errors=[],
        assignments=assignments,
        summary=summary,
        score=score,
        report=report,
        solver_stats={
            "status_name": solver.StatusName(status),
            "wall_time_seconds": round(solver.WallTime(), 3),
            "branches": solver.NumBranches(),
            "conflicts": solver.NumConflicts(),
            "quota_mode": "strict" if strict_quotas else "relaxed",
            "sexi_balance_mode": "guarded" if enforce_sexi_guard else "objective_only",
            "sexi_target_max_per_group": 3,
            "sexi_target_max_spread": 2,
        },
    )


def _apply_regular_quota_constraints(
    model: cp_model.CpModel,
    objective_tracker: ObjectiveTracker,
    strict_quotas: bool,
    normal_one_count: cp_model.IntVar,
    normal_two_count: cp_model.IntVar,
    period: int,
    group: int,
    settings,
) -> None:
    if strict_quotas:
        model.Add(normal_one_count == settings.regular_group_quota_one_period)
        model.Add(normal_two_count == settings.regular_group_quota_two_period)
        return

    for key_prefix, count_var, target in (
        ("one", normal_one_count, settings.regular_group_quota_one_period),
        ("two", normal_two_count, settings.regular_group_quota_two_period),
    ):
        shortfall = model.NewIntVar(0, target + 10, f"regular_{key_prefix}_shortfall_p{period}_g{group}")
        overflow = model.NewIntVar(0, target + 10, f"regular_{key_prefix}_overflow_p{period}_g{group}")
        model.Add(shortfall >= target - count_var)
        model.Add(overflow >= count_var - target)
        objective_tracker.add("quota_shortfall", shortfall)
        objective_tracker.add("quota_overflow", overflow)


def _apply_international_quota_constraints(
    model: cp_model.CpModel,
    objective_tracker: ObjectiveTracker,
    strict_quotas: bool,
    normal_one_count: cp_model.IntVar,
    normal_two_count: cp_model.IntVar,
    normal_total_count: cp_model.IntVar,
    period: int,
    group: int,
    settings,
) -> None:
    baseline_one = settings.regular_group_quota_one_period
    baseline_two = settings.regular_group_quota_two_period
    extra_total_target = settings.international_extra_mentors
    total_target = baseline_one + baseline_two + extra_total_target

    if strict_quotas:
        model.Add(normal_one_count >= baseline_one)
        model.Add(normal_two_count >= baseline_two)
        model.Add(normal_total_count == total_target)
    else:
        one_shortfall = model.NewIntVar(0, baseline_one, f"int_one_shortfall_p{period}_g{group}")
        two_shortfall = model.NewIntVar(0, baseline_two + extra_total_target, f"int_two_shortfall_p{period}_g{group}")
        total_shortfall = model.NewIntVar(0, total_target, f"int_total_shortfall_p{period}_g{group}")
        total_overflow = model.NewIntVar(0, total_target + 10, f"int_total_overflow_p{period}_g{group}")

        model.Add(one_shortfall >= baseline_one - normal_one_count)
        model.Add(two_shortfall >= baseline_two - normal_two_count)
        model.Add(total_shortfall >= total_target - normal_total_count)
        model.Add(total_overflow >= normal_total_count - total_target)

        objective_tracker.add("quota_shortfall", one_shortfall)
        objective_tracker.add("quota_shortfall", two_shortfall)
        objective_tracker.add("quota_shortfall", total_shortfall)
        objective_tracker.add("quota_overflow", total_overflow)

    extra_two_count = model.NewIntVar(0, baseline_two + extra_total_target, f"int_extra_two_p{period}_g{group}")
    model.AddMaxEquality(extra_two_count, [normal_two_count - baseline_two, 0])
    extra_two_shortfall = model.NewIntVar(0, extra_total_target, f"int_extra_two_shortfall_p{period}_g{group}")
    model.Add(extra_two_shortfall >= extra_total_target - extra_two_count)
    objective_tracker.add("international_extra_two_period_shortfall", extra_two_shortfall)


def _add_range_penalty(
    model: cp_model.CpModel,
    objective_tracker: ObjectiveTracker,
    key: str,
    periods: list[int],
    groups: list[int],
    assignment_vars: dict[tuple[int, int, int], cp_model.IntVar],
    mentor_indices: list[int],
    label: str,
) -> None:
    if not mentor_indices or len(groups) <= 1:
        return

    for period in periods:
        counts_by_group: list[cp_model.IntVar] = []
        for group in groups:
            count_var = model.NewIntVar(0, len(mentor_indices), f"{label}_count_p{period}_g{group}")
            model.Add(
                count_var == sum(assignment_vars[(mentor_idx, period, group)] for mentor_idx in mentor_indices)
            )
            counts_by_group.append(count_var)
        max_count = model.NewIntVar(0, len(mentor_indices), f"{label}_max_p{period}")
        min_count = model.NewIntVar(0, len(mentor_indices), f"{label}_min_p{period}")
        model.AddMaxEquality(max_count, counts_by_group)
        model.AddMinEquality(min_count, counts_by_group)
        range_var = model.NewIntVar(0, len(mentor_indices), f"{label}_range_p{period}")
        model.Add(range_var == max_count - min_count)
        objective_tracker.add(key, range_var)


def _add_strong_distribution_penalty(
    model: cp_model.CpModel,
    objective_tracker: ObjectiveTracker,
    key: str,
    periods: list[int],
    groups: list[int],
    count_vars: dict[tuple[int, int], cp_model.IntVar],
    upper_bound: int,
    label: str,
    hard_max_spread: int | None = None,
    hard_max_count: int | None = None,
) -> None:
    if not count_vars or len(groups) <= 1:
        return

    for period in periods:
        counts_by_group = [count_vars[(period, group)] for group in groups]
        max_count = model.NewIntVar(0, upper_bound, f"{label}_max_p{period}")
        min_count = model.NewIntVar(0, upper_bound, f"{label}_min_p{period}")
        range_var = model.NewIntVar(0, upper_bound, f"{label}_range_p{period}")
        model.AddMaxEquality(max_count, counts_by_group)
        model.AddMinEquality(min_count, counts_by_group)
        model.Add(range_var == max_count - min_count)

        if hard_max_spread is not None:
            model.Add(range_var <= hard_max_spread)
        if hard_max_count is not None:
            model.Add(max_count <= hard_max_count)

        objective_tracker.add(key, range_var)
        objective_tracker.add(key, max_count)

        for group in groups:
            overload = model.NewIntVar(0, upper_bound, f"{label}_overload_p{period}_g{group}")
            model.Add(overload >= count_vars[(period, group)] - 3)
            objective_tracker.add(key, overload)

        for left_index, right_index in combinations(groups, 2):
            diff_var = model.NewIntVar(0, upper_bound, f"{label}_diff_p{period}_g{left_index}_{right_index}")
            model.Add(diff_var >= count_vars[(period, left_index)] - count_vars[(period, right_index)])
            model.Add(diff_var >= count_vars[(period, right_index)] - count_vars[(period, left_index)])
            objective_tracker.add(key, diff_var)


def _build_group_results(
    mentors: list[Mentor],
    periods: list[int],
    groups: list[int],
    international_group_by_period: dict[int, int],
    assignment_vars: dict[tuple[int, int, int], cp_model.IntVar],
    leader_role_vars: dict[tuple[int, int, int, str], cp_model.IntVar],
    solver: cp_model.CpSolver,
) -> list[GroupResult]:
    results: list[GroupResult] = []
    for period in periods:
        for group in groups:
            assigned_indices = [
                mentor_idx
                for mentor_idx in range(len(mentors))
                if solver.Value(assignment_vars[(mentor_idx, period, group)])
            ]
            assigned = [mentors[mentor_idx] for mentor_idx in assigned_indices]
            assigned_rows: list[AssignedMentor] = []
            for mentor_idx in assigned_indices:
                mentor = mentors[mentor_idx]
                assigned_leader_role = None
                if mentor.category == MentorCategory.HOVDING:
                    if solver.Value(leader_role_vars[(mentor_idx, period, group, LeaderRole.HEAD.value)]):
                        assigned_leader_role = LeaderRole.HEAD
                    else:
                        assigned_leader_role = LeaderRole.VICE
                assigned_rows.append(
                    AssignedMentor(
                        id=mentor.id,
                        name=mentor.name,
                        category=mentor.category,
                        participation=mentor.participation,
                        gender=mentor.gender,
                        year=mentor.year,
                        normal_subrole=mentor.normal_subrole,
                        assigned_leader_role=assigned_leader_role,
                        requested_with=mentor.requested_with,
                    )
                )
            assigned_rows.sort(
                key=lambda mentor: (
                    mentor.category.value,
                    mentor.assigned_leader_role.value if mentor.assigned_leader_role else "",
                    mentor.participation.value,
                    mentor.name,
                )
            )
            results.append(
                GroupResult(
                    period=period + 1,
                    group_number=group + 1,
                    label=f"P{period + 1} Group {group + 1}",
                    is_international=group == international_group_by_period[period],
                    mentors=assigned_rows,
                    summary=_build_group_summary(assigned_rows),
                )
            )
    return results


def _build_group_summary(mentors: list[AssignedMentor]) -> GroupSummary:
    gender_breakdown: dict[str, int] = defaultdict(int)
    year_breakdown: dict[str, int] = defaultdict(int)
    normal_one_period_count = 0
    normal_two_period_count = 0
    sexi_count = 0
    leader_count = 0
    head_count = 0
    vice_count = 0
    event_count = 0

    for mentor in mentors:
        gender_breakdown[mentor.gender] += 1
        year_breakdown[mentor.year] += 1
        if mentor.category == MentorCategory.NORMAL and mentor.participation == ParticipationKind.ONE_PERIOD:
            normal_one_period_count += 1
        if mentor.category == MentorCategory.NORMAL and mentor.participation == ParticipationKind.TWO_PERIOD:
            normal_two_period_count += 1
        if mentor.category == MentorCategory.SEXI:
            sexi_count += 1
        if mentor.category == MentorCategory.HOVDING:
            leader_count += 1
            if mentor.assigned_leader_role == LeaderRole.HEAD:
                head_count += 1
            if mentor.assigned_leader_role == LeaderRole.VICE:
                vice_count += 1
        if mentor.category == MentorCategory.NORMAL and mentor.normal_subrole == NormalSubrole.EVENT:
            event_count += 1

    normal_total_count = normal_one_period_count + normal_two_period_count
    return GroupSummary(
        total_count=len(mentors),
        normal_one_period_count=normal_one_period_count,
        normal_two_period_count=normal_two_period_count,
        normal_total_count=normal_total_count,
        normal_extra_count=max(0, normal_total_count - normal_one_period_count - normal_two_period_count),
        sexi_count=sexi_count,
        leader_count=leader_count,
        head_count=head_count,
        vice_count=vice_count,
        event_count=event_count,
        gender_breakdown=dict(sorted(gender_breakdown.items())),
        year_breakdown=dict(sorted(year_breakdown.items())),
    )


def _build_request_outcomes(
    mentors: list[Mentor],
    assignments: list[GroupResult],
    periods: list[int],
) -> list[RequestOutcome]:
    membership_lookup: dict[tuple[str, int], set[str]] = {}
    for group in assignments:
        mentor_ids = {mentor.id for mentor in group.mentors}
        for mentor in group.mentors:
            membership_lookup[(mentor.id, group.period)] = mentor_ids

    outcomes: list[RequestOutcome] = []
    for mentor in mentors:
        if not mentor.requested_with:
            continue
        for period in periods:
            mentor_group = membership_lookup.get((mentor.id, period + 1))
            if mentor_group is None:
                continue
            matched_ids = sorted(requested_id for requested_id in mentor.requested_with if requested_id in mentor_group)
            outcomes.append(
                RequestOutcome(
                    mentor_id=mentor.id,
                    mentor_name=mentor.name,
                    period=period + 1,
                    requested_ids=mentor.requested_with,
                    matched_ids=matched_ids,
                    satisfied=bool(matched_ids),
                )
            )
    return outcomes


def _build_preferred_period_misses(
    mentors: list[Mentor],
    assignments: list[GroupResult],
) -> list[PreferredPeriodMiss]:
    assigned_period_by_mentor: dict[str, int] = {}
    for group in assignments:
        for mentor in group.mentors:
            if mentor.participation == ParticipationKind.ONE_PERIOD:
                assigned_period_by_mentor[mentor.id] = group.period

    misses: list[PreferredPeriodMiss] = []
    for mentor in mentors:
        if (
            mentor.category != MentorCategory.NORMAL
            or mentor.participation != ParticipationKind.ONE_PERIOD
            or mentor.preferred_period is None
        ):
            continue
        assigned_period = assigned_period_by_mentor.get(mentor.id)
        if assigned_period is not None and assigned_period != mentor.preferred_period:
            misses.append(
                PreferredPeriodMiss(
                    mentor_id=mentor.id,
                    mentor_name=mentor.name,
                    preferred_period=mentor.preferred_period,
                    assigned_period=assigned_period,
                )
            )
    misses.sort(key=lambda item: (item.assigned_period, item.mentor_name))
    return misses


def _build_repeated_groupmates(
    mentors: list[Mentor],
    assignments: list[GroupResult],
) -> list[RepeatedGroupmateDetail]:
    mentor_lookup = {mentor.id: mentor.name for mentor in mentors}
    groupmates_by_mentor_and_period: dict[tuple[str, int], set[str]] = {}
    for group in assignments:
        mentor_ids = {mentor.id for mentor in group.mentors}
        for mentor in group.mentors:
            groupmates_by_mentor_and_period[(mentor.id, group.period)] = mentor_ids - {mentor.id}

    details: list[RepeatedGroupmateDetail] = []
    for mentor in mentors:
        if (
            mentor.category != MentorCategory.NORMAL
            or mentor.participation != ParticipationKind.TWO_PERIOD
        ):
            continue
        repeated_with = sorted(
            groupmates_by_mentor_and_period.get((mentor.id, 1), set())
            & groupmates_by_mentor_and_period.get((mentor.id, 2), set())
        )
        details.append(
            RepeatedGroupmateDetail(
                mentor_id=mentor.id,
                mentor_name=mentor.name,
                repeated_groupmate_count=len(repeated_with),
                repeated_with=[mentor_lookup.get(repeated_id, repeated_id) for repeated_id in repeated_with],
            )
        )
    details.sort(key=lambda item: (-item.repeated_groupmate_count, item.mentor_name))
    return details


def _build_quota_deviations(
    scenario: ScenarioInput,
    assignments: list[GroupResult],
) -> list[QuotaDeviation]:
    settings = scenario.settings
    deviations: list[QuotaDeviation] = []
    for group in assignments:
        baseline_one = settings.regular_group_quota_one_period
        baseline_two = settings.regular_group_quota_two_period
        target_extra = settings.international_extra_mentors if group.is_international else 0
        target_total = baseline_one + baseline_two + target_extra
        actual_extra = max(0, group.summary.normal_total_count - baseline_one - baseline_two)
        extra_two = max(0, group.summary.normal_two_period_count - baseline_two)
        is_exact = (
            (
                not group.is_international
                and group.summary.normal_one_period_count == baseline_one
                and group.summary.normal_two_period_count == baseline_two
            )
            or (
                group.is_international
                and group.summary.normal_one_period_count >= baseline_one
                and group.summary.normal_two_period_count >= baseline_two
                and group.summary.normal_total_count == target_total
            )
        )
        if is_exact:
            continue
        deviations.append(
            QuotaDeviation(
                period=group.period,
                group_number=group.group_number,
                label=group.label,
                is_international=group.is_international,
                target_normal_one_period_baseline=baseline_one,
                actual_normal_one_period_count=group.summary.normal_one_period_count,
                target_normal_two_period_baseline=baseline_two,
                actual_normal_two_period_count=group.summary.normal_two_period_count,
                target_extra_normal_count=target_extra,
                actual_extra_normal_count=actual_extra,
                target_total_normal_count=target_total,
                actual_total_normal_count=group.summary.normal_total_count,
                extra_two_period_count=extra_two,
            )
        )
    return deviations


def _build_distribution_series(assignments: list[GroupResult]) -> list[DistributionSeries]:
    series: list[DistributionSeries] = []

    def add_series(category: str, value: str, counts_by_period: dict[int, list[int]]) -> None:
        all_counts = [count for counts in counts_by_period.values() for count in counts]
        series.append(
            DistributionSeries(
                category=category,
                value=value,
                overall_min_count=min(all_counts) if all_counts else 0,
                overall_max_count=max(all_counts) if all_counts else 0,
                overall_range=(max(all_counts) - min(all_counts)) if all_counts else 0,
                per_period=[
                    DistributionPeriodSummary(
                        period=period,
                        counts_by_group=counts,
                        min_count=min(counts) if counts else 0,
                        max_count=max(counts) if counts else 0,
                        average_count=round(sum(counts) / len(counts), 2) if counts else 0.0,
                    )
                    for period, counts in sorted(counts_by_period.items())
                ],
            )
        )

    add_series(
        "sexi",
        "sexi mentors",
        {
            period: [group.summary.sexi_count for group in assignments if group.period == period]
            for period in sorted({group.period for group in assignments})
        },
    )
    add_series(
        "event",
        "event mentors",
        {
            period: [group.summary.event_count for group in assignments if group.period == period]
            for period in sorted({group.period for group in assignments})
        },
    )

    for category_name, extractor in (
        ("gender", lambda group: group.summary.gender_breakdown),
        ("year", lambda group: group.summary.year_breakdown),
    ):
        values = sorted({key for group in assignments for key in extractor(group).keys()})
        for value in values:
            add_series(
                category_name,
                value,
                {
                    period: [extractor(group).get(value, 0) for group in assignments if group.period == period]
                    for period in sorted({group.period for group in assignments})
                },
            )

    return series


def _build_solve_summary(
    scenario: ScenarioInput,
    assignments: list[GroupResult],
    quota_deviations: list[QuotaDeviation],
    request_outcomes: list[RequestOutcome],
    preferred_period_misses: list[PreferredPeriodMiss],
    repeated_groupmates: list[RepeatedGroupmateDetail],
    international_group_by_period: dict[int, int],
) -> SolveSummary:
    mentor_assignments: dict[str, list[int]] = defaultdict(list)
    leader_roles: dict[str, list[LeaderRole]] = defaultdict(list)
    international_assignments: list[tuple[str, int]] = []

    for group in assignments:
        for mentor in group.mentors:
            mentor_assignments[mentor.id].append(group.period)
            if mentor.assigned_leader_role is not None:
                leader_roles[mentor.id].append(mentor.assigned_leader_role)
            if group.is_international:
                international_assignments.append((mentor.id, group.period))

    blocked_pair_violations = 0
    for blocked_pair in scenario.blocked_pairs:
        for period in (1, 2):
            left_group = next(
                (
                    group.group_number
                    for group in assignments
                    if group.period == period and any(mentor.id == blocked_pair.mentor_a for mentor in group.mentors)
                ),
                None,
            )
            right_group = next(
                (
                    group.group_number
                    for group in assignments
                    if group.period == period and any(mentor.id == blocked_pair.mentor_b for mentor in group.mentors)
                ),
                None,
            )
            if left_group is not None and left_group == right_group:
                blocked_pair_violations += 1

    one_period_assignment_violations = 0
    two_period_assignment_violations = 0
    leader_assignment_violations = 0
    leader_role_violations = 0
    for mentor in scenario.mentors:
        periods_assigned = sorted(mentor_assignments.get(mentor.id, []))
        if mentor.participation == ParticipationKind.ONE_PERIOD and len(periods_assigned) != 1:
            one_period_assignment_violations += 1
        if mentor.participation == ParticipationKind.TWO_PERIOD and periods_assigned != [1, 2]:
            two_period_assignment_violations += 1
        if mentor.category == MentorCategory.HOVDING:
            if periods_assigned != [1, 2]:
                leader_assignment_violations += 1
            roles = leader_roles.get(mentor.id, [])
            if sorted(role.value for role in roles) != sorted([LeaderRole.HEAD.value, LeaderRole.VICE.value]):
                leader_role_violations += 1

    leader_group_role_violations = sum(
        1
        for group in assignments
        if group.summary.leader_count != 2 or group.summary.head_count != 1 or group.summary.vice_count != 1
    )

    nonpreferred_international_assignments = 0
    nonpreferred_international_repeat_violations = 0
    preferred_international_total = 0
    preferred_international_satisfied = 0
    international_periods_by_mentor: dict[str, list[int]] = defaultdict(list)
    for mentor_id, period in international_assignments:
        international_periods_by_mentor[mentor_id].append(period)

    for mentor in scenario.mentors:
        assigned_periods = international_periods_by_mentor.get(mentor.id, [])
        if mentor.prefers_international:
            preferred_international_total += 1
            if assigned_periods:
                preferred_international_satisfied += 1
        else:
            nonpreferred_international_assignments += len(assigned_periods)
            if len(assigned_periods) > 1:
                nonpreferred_international_repeat_violations += 1

    event_absolute_violations = sum(
        1
        for group in assignments
        if group.summary.event_count > scenario.settings.absolute_max_event_mentors_per_group
    )

    exact_quota_group_count = len(assignments) - len(quota_deviations)
    repeated_pair_count = sum(detail.repeated_groupmate_count for detail in repeated_groupmates) // 2
    requested_partner_satisfied = sum(1 for outcome in request_outcomes if outcome.satisfied)
    preferred_period_total = sum(
        1
        for mentor in scenario.mentors
        if mentor.category == MentorCategory.NORMAL
        and mentor.participation == ParticipationKind.ONE_PERIOD
        and mentor.preferred_period is not None
    )

    return SolveSummary(
        mentor_count=len(scenario.mentors),
        group_count=len(assignments),
        total_assignments=sum(len(group.mentors) for group in assignments),
        international_group_count=len(international_group_by_period),
        blocked_pair_count=len(scenario.blocked_pairs),
        blocked_pair_violations=blocked_pair_violations,
        one_period_assignment_violations=one_period_assignment_violations,
        two_period_assignment_violations=two_period_assignment_violations,
        leader_assignment_violations=leader_assignment_violations,
        leader_role_violations=leader_role_violations,
        leader_group_role_violations=leader_group_role_violations,
        nonpreferred_international_repeat_violations=nonpreferred_international_repeat_violations,
        event_absolute_violations=event_absolute_violations,
        exact_quota_group_count=exact_quota_group_count,
        quota_deviation_group_count=len(quota_deviations),
        preferred_international_satisfied=preferred_international_satisfied,
        preferred_international_total=preferred_international_total,
        nonpreferred_international_assignments=nonpreferred_international_assignments,
        requested_partner_satisfied=requested_partner_satisfied,
        requested_partner_total=len(request_outcomes),
        preferred_period_satisfied=preferred_period_total - len(preferred_period_misses),
        preferred_period_total=preferred_period_total,
        repeated_groupmate_pair_count=repeated_pair_count,
    )
