export type MentorCategory = "normal" | "sexi" | "hovding";
export type ParticipationKind = "one_period" | "two_period";
export type NormalSubrole = "normal" | "event" | "international";
export type LeaderRole = "head" | "vice";
export type SolveStatus = "optimal" | "feasible" | "infeasible";
export type IssueSeverity = "error" | "warning";
export type RuleKind = "hard" | "soft";
export type RuleStatus =
  | "satisfied"
  | "partially_satisfied"
  | "violated"
  | "not_applicable";

export interface Mentor {
  id: string;
  name: string;
  category: MentorCategory;
  participation: ParticipationKind;
  preferred_period: number | null;
  gender: string;
  year: string;
  normal_subrole: NormalSubrole | null;
  requested_with: string[];
}

export interface BlockedPair {
  mentor_a: string;
  mentor_b: string;
}

export interface ScenarioSettings {
  period_count: number;
  groups_per_period: number;
  regular_group_quota_one_period: number;
  regular_group_quota_two_period: number;
  international_extra_mentors: number;
  international_group_numbers: Record<number, number>;
  ideal_max_event_mentors_per_group: number;
  absolute_max_event_mentors_per_group: number;
  max_solver_time_seconds: number;
  enforce_strict_quotas_when_feasible: boolean;
}

export interface SolverWeights {
  quota_shortfall: number;
  quota_overflow: number;
  international_extra_two_period_shortfall: number;
  international_preference: number;
  nonpreferred_international: number;
  request_missing: number;
  preferred_period_miss: number;
  repeated_groupmates: number;
  event_second_mentor: number;
  event_evenness: number;
  sexi_evenness: number;
  balance_gender: number;
  balance_year: number;
}

export interface ScenarioInput {
  mentors: Mentor[];
  blocked_pairs: BlockedPair[];
  settings: ScenarioSettings;
  weights: SolverWeights;
}

export interface ScenarioIssue {
  code: string;
  severity: IssueSeverity;
  message: string;
  details: string | null;
}

export interface ValidationSummary {
  mentor_count: number;
  blocked_pair_count: number;
  normal_one_period_supply: number;
  normal_one_period_target: number;
  normal_two_period_supply: number;
  normal_two_period_target: number;
  sexi_supply: number;
  leader_supply: number;
  leader_target: number;
  event_assignment_supply: number;
  event_ideal_capacity: number;
  event_absolute_capacity: number;
  international_preference_count: number;
}

export interface ValidationResponse {
  ok: boolean;
  errors: ScenarioIssue[];
  warnings: ScenarioIssue[];
  summary: ValidationSummary;
}

export interface AssignedMentor {
  id: string;
  name: string;
  category: MentorCategory;
  participation: ParticipationKind;
  gender: string;
  year: string;
  normal_subrole: NormalSubrole | null;
  assigned_leader_role: LeaderRole | null;
  requested_with: string[];
}

export interface GroupSummary {
  total_count: number;
  normal_one_period_count: number;
  normal_two_period_count: number;
  normal_total_count: number;
  normal_extra_count: number;
  sexi_count: number;
  leader_count: number;
  head_count: number;
  vice_count: number;
  event_count: number;
  gender_breakdown: Record<string, number>;
  year_breakdown: Record<string, number>;
}

export interface GroupResult {
  period: number;
  group_number: number;
  label: string;
  is_international: boolean;
  mentors: AssignedMentor[];
  summary: GroupSummary;
}

export interface RequestOutcome {
  mentor_id: string;
  mentor_name: string;
  period: number;
  requested_ids: string[];
  matched_ids: string[];
  satisfied: boolean;
}

export interface PreferredPeriodMiss {
  mentor_id: string;
  mentor_name: string;
  preferred_period: number;
  assigned_period: number;
}

export interface RepeatedGroupmateDetail {
  mentor_id: string;
  mentor_name: string;
  repeated_groupmate_count: number;
  repeated_with: string[];
}

export interface QuotaDeviation {
  period: number;
  group_number: number;
  label: string;
  is_international: boolean;
  target_normal_one_period_baseline: number;
  actual_normal_one_period_count: number;
  target_normal_two_period_baseline: number;
  actual_normal_two_period_count: number;
  target_extra_normal_count: number;
  actual_extra_normal_count: number;
  target_total_normal_count: number;
  actual_total_normal_count: number;
  extra_two_period_count: number;
}

export interface RuleEvaluation {
  code: string;
  title: string;
  priority: number | null;
  kind: RuleKind;
  status: RuleStatus;
  summary: string;
  details: string[];
}

export interface DistributionPeriodSummary {
  period: number;
  counts_by_group: number[];
  min_count: number;
  max_count: number;
  average_count: number;
}

export interface DistributionSeries {
  category: string;
  value: string;
  overall_min_count: number;
  overall_max_count: number;
  overall_range: number;
  per_period: DistributionPeriodSummary[];
}

export interface ScoreComponent {
  key: string;
  label: string;
  category: string;
  weight: number;
  raw_value: number;
  weighted_penalty: number;
}

export interface ScoreBreakdown {
  components: ScoreComponent[];
  grouped_penalties: Record<string, number>;
  total_penalty: number;
}

export interface SolveSummary {
  mentor_count: number;
  group_count: number;
  total_assignments: number;
  international_group_count: number;
  blocked_pair_count: number;
  blocked_pair_violations: number;
  one_period_assignment_violations: number;
  two_period_assignment_violations: number;
  leader_assignment_violations: number;
  leader_role_violations: number;
  leader_group_role_violations: number;
  nonpreferred_international_repeat_violations: number;
  event_absolute_violations: number;
  exact_quota_group_count: number;
  quota_deviation_group_count: number;
  preferred_international_satisfied: number;
  preferred_international_total: number;
  nonpreferred_international_assignments: number;
  requested_partner_satisfied: number;
  requested_partner_total: number;
  preferred_period_satisfied: number;
  preferred_period_total: number;
  repeated_groupmate_pair_count: number;
}

export interface CompromiseReport {
  overview: string[];
  hard_constraint_statuses: RuleEvaluation[];
  soft_goal_statuses: RuleEvaluation[];
  compromises: string[];
  diagnostics: string[];
  quota_deviations: QuotaDeviation[];
  request_outcomes: RequestOutcome[];
  preferred_period_misses: PreferredPeriodMiss[];
  repeated_groupmates: RepeatedGroupmateDetail[];
  distributions: DistributionSeries[];
  metadata: Record<string, unknown>;
}

export interface SolveResponse {
  status: SolveStatus;
  objective_value: number | null;
  warnings: ScenarioIssue[];
  errors: ScenarioIssue[];
  assignments: GroupResult[];
  summary: SolveSummary | null;
  score: ScoreBreakdown | null;
  report: CompromiseReport | null;
  solver_stats: Record<string, unknown>;
}

export interface SavedProposalSummary {
  status: string;
  objective_value: number | null;
  group_count: number;
  requested_partner_satisfied: number;
  requested_partner_total: number;
  preferred_period_satisfied: number;
  preferred_period_total: number;
  exact_quota_group_count: number;
  total_group_count: number;
}

export interface SavedProposal {
  id: string;
  name: string;
  created_at: string;
  scenario: ScenarioInput;
  validation: ValidationResponse | null;
  solution: SolveResponse;
  summary: SavedProposalSummary;
}

export interface WorkspaceState {
  scenario: ScenarioInput;
  saved_proposals: SavedProposal[];
}

export function createEmptyScenario(): ScenarioInput {
  return {
    mentors: [],
    blocked_pairs: [],
    settings: {
      period_count: 2,
      groups_per_period: 10,
      regular_group_quota_one_period: 2,
      regular_group_quota_two_period: 5,
      international_extra_mentors: 3,
      international_group_numbers: { 1: 1, 2: 1 },
      ideal_max_event_mentors_per_group: 1,
      absolute_max_event_mentors_per_group: 2,
      max_solver_time_seconds: 20,
      enforce_strict_quotas_when_feasible: true
    },
    weights: {
      quota_shortfall: 1_000_000,
      quota_overflow: 850_000,
      international_extra_two_period_shortfall: 80_000,
      international_preference: 150_000,
      nonpreferred_international: 20_000,
      request_missing: 250_000,
      preferred_period_miss: 8_000,
      repeated_groupmates: 150,
      event_second_mentor: 10_000,
      event_evenness: 1_000,
      sexi_evenness: 5_000,
      balance_gender: 250,
      balance_year: 250
    }
  };
}

export function createBlankMentor(sequence: number): Mentor {
  return {
    id: `M${String(sequence).padStart(3, "0")}`,
    name: `New Mentor ${sequence}`,
    category: "normal",
    participation: "one_period",
    preferred_period: 1,
    gender: "unspecified",
    year: "1",
    normal_subrole: "normal",
    requested_with: []
  };
}

export function createBlankBlockedPair(): BlockedPair {
  return {
    mentor_a: "",
    mentor_b: ""
  };
}
