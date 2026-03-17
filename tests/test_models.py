import pytest
from pydantic import ValidationError

from backend.app.models import (
    BlockedPair,
    Mentor,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
    ScenarioInput,
)


def test_duplicate_mentor_ids_are_rejected():
    with pytest.raises(ValidationError):
        ScenarioInput(
            mentors=[
                Mentor(
                    id="m1",
                    name="A",
                    category=MentorCategory.NORMAL,
                    participation=ParticipationKind.ONE_PERIOD,
                    preferred_period=1,
                ),
                Mentor(
                    id="m1",
                    name="B",
                    category=MentorCategory.NORMAL,
                    participation=ParticipationKind.ONE_PERIOD,
                    preferred_period=2,
                ),
            ]
        )


def test_non_normal_cannot_have_normal_subrole():
    with pytest.raises(ValidationError):
        Mentor(
            id="s1",
            name="Sexi",
            category=MentorCategory.SEXI,
            participation=ParticipationKind.TWO_PERIOD,
            normal_subrole=NormalSubrole.EVENT,
        )


def test_hovding_must_be_two_period():
    with pytest.raises(ValidationError):
        Mentor(
            id="h1",
            name="Leader",
            category=MentorCategory.HOVDING,
            participation=ParticipationKind.ONE_PERIOD,
            preferred_period=1,
        )


def test_requested_with_blocked_pair_conflict_is_rejected():
    with pytest.raises(ValidationError):
        ScenarioInput(
            mentors=[
                Mentor(
                    id="m1",
                    name="A",
                    category=MentorCategory.NORMAL,
                    participation=ParticipationKind.ONE_PERIOD,
                    preferred_period=1,
                    requested_with=["m2"],
                ),
                Mentor(
                    id="m2",
                    name="B",
                    category=MentorCategory.NORMAL,
                    participation=ParticipationKind.ONE_PERIOD,
                    preferred_period=2,
                ),
            ],
            blocked_pairs=[BlockedPair(mentor_a="m1", mentor_b="m2")],
        )
