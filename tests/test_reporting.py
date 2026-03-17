from tests.test_solver import build_sexi_balance_scenario, build_small_scenario
from backend.app.solver import solve_scenario


def test_report_contains_leader_and_request_sections():
    solution = solve_scenario(build_small_scenario())
    assert solution.report is not None
    titles = {rule.code for rule in solution.report.hard_constraint_statuses}
    assert "leader_structure" in titles
    assert "blocked_pairs" in titles
    assert "international_hard_assignments" in titles
    assert solution.report.request_outcomes
    assert solution.report.repeated_groupmates


def test_report_exposes_sexi_and_requested_partner_summaries():
    solution = solve_scenario(build_sexi_balance_scenario())

    assert solution.report is not None
    sexi_target = solution.report.metadata["sexi_target"]
    assert sexi_target["within_target"] is True
    assert sexi_target["max_per_group"] == 3
    assert sexi_target["max_spread"] == 2

    requested_summary = solution.report.metadata["requested_partner_summary"]
    assert requested_summary["period_1"]["total"] == 0
    assert requested_summary["period_2"]["total"] == 0

    distribution_rule = next(
        rule for rule in solution.report.soft_goal_statuses if rule.code == "distribution_balance"
    )
    assert any("Sexi distribution" in detail for detail in distribution_rule.details)
