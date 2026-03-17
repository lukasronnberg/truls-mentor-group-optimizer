from backend.app.import_export import groups_to_csv, parse_blocked_pairs_csv, parse_mentors_csv
from backend.app.models import (
    AssignedMentor,
    GroupResult,
    GroupSummary,
    LeaderRole,
    MentorCategory,
    NormalSubrole,
    ParticipationKind,
)


def test_parse_mentors_csv():
    csv_text = """id,name,category,participation,preferred_period,gender,year,normal_subrole,requested_with
M1,Alice,normal,one_period,1,woman,1,international,M2
M2,Bob,sexi,two_period,,man,2,, 
"""
    mentors = parse_mentors_csv(csv_text)
    assert len(mentors) == 2
    assert mentors[0].participation == ParticipationKind.ONE_PERIOD
    assert mentors[1].category == MentorCategory.SEXI
    assert mentors[0].requested_with == ["M2"]


def test_parse_blocked_pairs_csv():
    csv_text = """mentor_a,mentor_b
M1,M2
M3,M4
"""
    blocked_pairs = parse_blocked_pairs_csv(csv_text)
    assert len(blocked_pairs) == 2
    assert blocked_pairs[0].mentor_a == "M1"


def test_groups_to_csv():
    csv_output = groups_to_csv(
        [
            GroupResult(
                period=1,
                group_number=1,
                label="P1 Group 1",
                is_international=True,
                mentors=[
                    AssignedMentor(
                        id="H1",
                        name="Leader",
                        category=MentorCategory.HOVDING,
                        participation=ParticipationKind.TWO_PERIOD,
                        gender="woman",
                        year="leader",
                        normal_subrole=None,
                        assigned_leader_role=LeaderRole.HEAD,
                        requested_with=["M2"],
                    )
                ],
                summary=GroupSummary(
                    total_count=1,
                    normal_one_period_count=0,
                    normal_two_period_count=0,
                    normal_total_count=0,
                    normal_extra_count=0,
                    sexi_count=0,
                    leader_count=1,
                    head_count=1,
                    vice_count=0,
                    event_count=0,
                    gender_breakdown={"woman": 1},
                    year_breakdown={"leader": 1},
                ),
            )
        ]
    )
    assert "assigned_leader_role" in csv_output
    assert "Leader" in csv_output
