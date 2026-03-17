from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from ortools.sat.python import cp_model

from .models import ScoreBreakdown, ScoreComponent, SolverWeights


@dataclass(frozen=True)
class ScoreSpec:
    key: str
    label: str
    category: str
    weight_field: str


SCORE_SPECS: dict[str, ScoreSpec] = {
    "quota_shortfall": ScoreSpec(
        key="quota_shortfall",
        label="Quota shortfall",
        category="Quota and International",
        weight_field="quota_shortfall",
    ),
    "quota_overflow": ScoreSpec(
        key="quota_overflow",
        label="Quota overflow",
        category="Quota and International",
        weight_field="quota_overflow",
    ),
    "international_extra_two_period_shortfall": ScoreSpec(
        key="international_extra_two_period_shortfall",
        label="International extra two-period shortfall",
        category="Quota and International",
        weight_field="international_extra_two_period_shortfall",
    ),
    "international_preference": ScoreSpec(
        key="international_preference",
        label="Missed international preference",
        category="Quota and International",
        weight_field="international_preference",
    ),
    "nonpreferred_international": ScoreSpec(
        key="nonpreferred_international",
        label="Non-requested international assignment",
        category="Quota and International",
        weight_field="nonpreferred_international",
    ),
    "request_missing": ScoreSpec(
        key="request_missing",
        label="No requested partner in participated period",
        category="Preferences",
        weight_field="request_missing",
    ),
    "preferred_period_miss": ScoreSpec(
        key="preferred_period_miss",
        label="Missed preferred period",
        category="Preferences",
        weight_field="preferred_period_miss",
    ),
    "repeated_groupmates": ScoreSpec(
        key="repeated_groupmates",
        label="Repeated overlap beyond one repeated two-period groupmate",
        category="Preferences",
        weight_field="repeated_groupmates",
    ),
    "event_second_mentor": ScoreSpec(
        key="event_second_mentor",
        label="Second event mentor in a group",
        category="Distribution",
        weight_field="event_second_mentor",
    ),
    "event_evenness": ScoreSpec(
        key="event_evenness",
        label="Event mentor distribution unevenness",
        category="Distribution",
        weight_field="event_evenness",
    ),
    "sexi_evenness": ScoreSpec(
        key="sexi_evenness",
        label="Sexi mentor spread, overload, and max-load unevenness",
        category="Distribution",
        weight_field="sexi_evenness",
    ),
    "balance_gender": ScoreSpec(
        key="balance_gender",
        label="Gender balance unevenness",
        category="Distribution",
        weight_field="balance_gender",
    ),
    "balance_year": ScoreSpec(
        key="balance_year",
        label="Year balance unevenness",
        category="Distribution",
        weight_field="balance_year",
    ),
}


class ObjectiveTracker:
    def __init__(self, weights: SolverWeights) -> None:
        self.weights = weights
        self.expressions: dict[str, list[cp_model.LinearExprT]] = defaultdict(list)

    def add(self, key: str, expression: cp_model.LinearExprT) -> None:
        spec = SCORE_SPECS[key]
        weight = getattr(self.weights, spec.weight_field)
        if weight:
            self.expressions[key].append(expression)

    def objective_expression(self) -> cp_model.LinearExprT:
        return sum(
            getattr(self.weights, SCORE_SPECS[key].weight_field) * expression
            for key, expressions in self.expressions.items()
            for expression in expressions
        )

    def build_breakdown(self, solver: cp_model.CpSolver) -> ScoreBreakdown:
        components: list[ScoreComponent] = []
        grouped_penalties: dict[str, int] = defaultdict(int)
        total_penalty = 0

        for key, spec in SCORE_SPECS.items():
            raw_value = sum(solver.Value(expression) for expression in self.expressions.get(key, []))
            weight = getattr(self.weights, spec.weight_field)
            weighted_penalty = raw_value * weight
            components.append(
                ScoreComponent(
                    key=key,
                    label=spec.label,
                    category=spec.category,
                    weight=weight,
                    raw_value=raw_value,
                    weighted_penalty=weighted_penalty,
                )
            )
            grouped_penalties[spec.category] += weighted_penalty
            total_penalty += weighted_penalty

        return ScoreBreakdown(
            components=components,
            grouped_penalties=dict(grouped_penalties),
            total_penalty=total_penalty,
        )
