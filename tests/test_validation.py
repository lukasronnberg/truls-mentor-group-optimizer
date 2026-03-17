from backend.app.models import (
    Mentor,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    ScenarioInput,
    ScenarioSettings,
)
from backend.app.validation import analyze_scenario


def test_validation_flags_leader_count_error():
    scenario = ScenarioInput(
        mentors=[
            Mentor(
                id="N1",
                name="Normal",
                category=MentorCategory.NORMAL,
                participation=ParticipationKind.ONE_PERIOD,
                preferred_period=1,
            ),
            Mentor(
                id="H1",
                name="Leader",
                category=MentorCategory.HOVDING,
                participation=ParticipationKind.TWO_PERIOD,
            ),
        ],
        settings=ScenarioSettings(
            groups_per_period=1,
            regular_group_quota_one_period=0,
            regular_group_quota_two_period=0,
            international_extra_mentors=0,
            international_group_numbers={1: 1, 2: 1},
        ),
    )
    result = analyze_scenario(scenario)
    assert not result.ok
    assert any(issue.code == "leader_supply_mismatch" for issue in result.errors)


def test_validation_flags_tight_event_capacity_warning():
    mentors = [
        Mentor(
            id=f"E{index}",
            name=f"Event {index}",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.ONE_PERIOD,
            preferred_period=1 if index < 2 else 2,
            normal_subrole=NormalSubrole.EVENT,
        )
        for index in range(3)
    ]
    scenario = ScenarioInput(
        mentors=mentors
        + [
            Mentor(
                id=f"H{index}",
                name=f"Leader {index}",
                category=MentorCategory.HOVDING,
                participation=ParticipationKind.TWO_PERIOD,
            )
            for index in range(1, 3)
        ],
        settings=ScenarioSettings(
            groups_per_period=1,
            regular_group_quota_one_period=0,
            regular_group_quota_two_period=0,
            international_extra_mentors=0,
            international_group_numbers={1: 1, 2: 1},
        ),
    )
    result = analyze_scenario(scenario)
    assert any(issue.code == "event_capacity_tight" for issue in result.warnings)


def test_validation_warns_when_no_international_subrole_exists():
    scenario = ScenarioInput(
        mentors=[
            Mentor(
                id=f"H{index}",
                name=f"Leader {index}",
                category=MentorCategory.HOVDING,
                participation=ParticipationKind.TWO_PERIOD,
            )
            for index in range(1, 3)
        ],
        settings=ScenarioSettings(
            groups_per_period=1,
            regular_group_quota_one_period=0,
            regular_group_quota_two_period=0,
            international_extra_mentors=0,
            international_group_numbers={1: 1, 2: 1},
        ),
    )
    result = analyze_scenario(scenario)
    assert any(issue.code == "no_international_preferences" for issue in result.warnings)


def test_validation_flags_impossible_hard_international_capacity():
    mentors = [
        Mentor(
            id="I1",
            name="Intis One",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.TWO_PERIOD,
            normal_subrole=NormalSubrole.INTERNATIONAL,
        ),
        Mentor(
            id="I2",
            name="Intis Two",
            category=MentorCategory.NORMAL,
            participation=ParticipationKind.TWO_PERIOD,
            normal_subrole=NormalSubrole.INTERNATIONAL,
        ),
        Mentor(
            id="H1",
            name="Leader One",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.TWO_PERIOD,
        ),
        Mentor(
            id="H2",
            name="Leader Two",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.TWO_PERIOD,
        ),
    ]
    scenario = ScenarioInput(
        mentors=mentors,
        settings=ScenarioSettings(
            groups_per_period=1,
            regular_group_quota_one_period=0,
            regular_group_quota_two_period=1,
            international_extra_mentors=0,
            international_group_numbers={1: 1, 2: 1},
        ),
    )
    result = analyze_scenario(scenario)
    assert any(issue.code == "international_hard_assignment_impossible" for issue in result.errors)
