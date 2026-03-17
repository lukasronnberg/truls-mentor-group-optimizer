from backend.app.models import (
    BlockedPair,
    Mentor,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    ScenarioInput,
    ScenarioSettings,
)
from backend.app.solver import solve_scenario


def build_small_scenario() -> ScenarioInput:
    mentors = [
        Mentor(
            id="N1",
            name="Normal One",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.TWO_PERIOD,
            gender="woman",
            year="1",
            requested_with=["O1"],
        ),
        Mentor(
            id="N2",
            name="Normal Two",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.TWO_PERIOD,
            gender="man",
            year="2",
        ),
        Mentor(
            id="O1",
            name="One One",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.ONE_PERIOD,
            preferred_period=1,
            gender="woman",
            year="1",
            normal_subrole=NormalSubrole.INTERNATIONAL,
            requested_with=["N1"],
        ),
        Mentor(
            id="O2",
            name="One Two",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.ONE_PERIOD,
            preferred_period=2,
            gender="man",
            year="2",
        ),
        Mentor(
            id="S1",
            name="Sexi",
            category=MentorCategory.SEXI,
            participation=ParticipationKind.ONE_PERIOD,
            preferred_period=1,
            gender="woman",
            year="3",
        ),
        Mentor(
            id="H1",
            name="Leader HeadVice One",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.TWO_PERIOD,
            gender="woman",
            year="leader",
        ),
        Mentor(
            id="H2",
            name="Leader HeadVice Two",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.TWO_PERIOD,
            gender="man",
            year="leader",
        ),
        Mentor(
            id="H3",
            name="Leader HeadVice Three",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.TWO_PERIOD,
            gender="woman",
            year="leader",
        ),
        Mentor(
            id="H4",
            name="Leader HeadVice Four",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.TWO_PERIOD,
            gender="man",
            year="leader",
        ),
    ]
    return ScenarioInput(
        mentors=mentors,
        blocked_pairs=[BlockedPair(mentor_a="N1", mentor_b="N2")],
        settings=ScenarioSettings(
            groups_per_period=2,
            regular_group_quota_one_period=1,
            regular_group_quota_two_period=1,
            international_extra_mentors=0,
            international_group_numbers={1: 1, 2: 2},
            max_solver_time_seconds=5,
        ),
    )


def build_relaxed_quota_scenario() -> ScenarioInput:
    scenario = build_small_scenario()
    return scenario.model_copy(
        update={
            "settings": scenario.settings.model_copy(
                update={"international_extra_mentors": 1}
            )
        }
    )


def build_sexi_balance_scenario() -> ScenarioInput:
    mentors = [
        Mentor(
            id=f"N{index}",
            name=f"Normal {index}",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.TWO_PERIOD,
            gender="mixed",
            year="1",
        )
        for index in range(1, 5)
    ]
    mentors.extend(
        [
            Mentor(
                id=f"S{index}",
                name=f"Sexi {index}",
                category=MentorCategory.SEXI,
                participation=ParticipationKind.ONE_PERIOD,
                preferred_period=1,
                gender="mixed",
                year="2",
            )
            for index in range(1, 9)
        ]
    )
    mentors.extend(
        [
            Mentor(
                id=f"H{index}",
                name=f"Leader {index}",
                category=MentorCategory.HOVDING,
                participation=ParticipationKind.TWO_PERIOD,
                gender="mixed",
                year="leader",
            )
            for index in range(1, 9)
        ]
    )
    return ScenarioInput(
        mentors=mentors,
        settings=ScenarioSettings(
            groups_per_period=4,
            regular_group_quota_one_period=0,
            regular_group_quota_two_period=1,
            international_extra_mentors=0,
            international_group_numbers={1: 1, 2: 1},
            max_solver_time_seconds=5,
        ),
    )


def test_solver_respects_hard_constraints_and_leader_roles():
    solution = solve_scenario(build_small_scenario())
    assert solution.status in {"optimal", "feasible"}

    mentor_assignments = {}
    leader_roles = {}
    for group in solution.assignments:
        mentor_ids = {mentor.id for mentor in group.mentors}
        assert not {"N1", "N2"}.issubset(mentor_ids)
        assert group.summary.leader_count == 2
        assert group.summary.head_count == 1
        assert group.summary.vice_count == 1
        for mentor in group.mentors:
            mentor_assignments.setdefault(mentor.id, []).append((group.period, group.group_number))
            if mentor.assigned_leader_role:
                leader_roles.setdefault(mentor.id, []).append(mentor.assigned_leader_role)

    assert len(mentor_assignments["N1"]) == 2
    assert len(mentor_assignments["N2"]) == 2
    assert len(mentor_assignments["O1"]) == 1
    assert len(mentor_assignments["O2"]) == 1
    assert len(mentor_assignments["S1"]) == 1
    for leader_id in {"H1", "H2", "H3", "H4"}:
        roles = sorted(role.value for role in leader_roles[leader_id])
        assert roles == ["head", "vice"]


def test_solver_falls_back_to_relaxed_quota_mode_when_strict_is_impossible():
    solution = solve_scenario(build_relaxed_quota_scenario())
    assert solution.status in {"optimal", "feasible"}
    assert solution.summary is not None
    assert solution.solver_stats["quota_mode"] == "relaxed"
    assert solution.summary.quota_deviation_group_count > 0


def test_international_subrole_is_enforced_as_hard_assignment():
    solution = solve_scenario(build_small_scenario())
    assert solution.status in {"optimal", "feasible"}

    international_by_period = {
        group.period: {mentor.id for mentor in group.mentors}
        for group in solution.assignments
        if group.is_international
    }

    assert "O1" in international_by_period[1]


def test_solver_keeps_sexi_distribution_tightly_balanced_when_feasible():
    solution = solve_scenario(build_sexi_balance_scenario())

    assert solution.status in {"optimal", "feasible"}
    assert solution.solver_stats["sexi_balance_mode"] == "guarded"

    for period in (1, 2):
        sexi_counts = [
            group.summary.sexi_count
            for group in solution.assignments
            if group.period == period
        ]
        assert max(sexi_counts) - min(sexi_counts) <= 1
        assert max(sexi_counts) <= 2
