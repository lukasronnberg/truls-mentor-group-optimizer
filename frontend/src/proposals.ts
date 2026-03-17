import type { SavedProposal, SavedProposalSummary, ScenarioInput, SolveResponse, ValidationResponse } from "./types";

export function buildProposalRecord(
  scenario: ScenarioInput,
  validation: ValidationResponse | null,
  solution: SolveResponse,
  sequenceNumber: number,
  name?: string
): SavedProposal {
  const createdAt = new Date().toISOString();
  return {
    id: typeof crypto !== "undefined" && "randomUUID" in crypto ? crypto.randomUUID() : `proposal-${Date.now()}`,
    name: name?.trim() || defaultProposalName(createdAt, sequenceNumber),
    created_at: createdAt,
    scenario,
    validation,
    solution,
    summary: summarizeProposal(solution)
  };
}

export function renameProposal(proposals: SavedProposal[], proposalId: string, nextName: string): SavedProposal[] {
  return proposals.map((proposal) =>
    proposal.id === proposalId ? { ...proposal, name: nextName.trim() || proposal.name } : proposal
  );
}

export function deleteProposal(proposals: SavedProposal[], proposalId: string): SavedProposal[] {
  return proposals.filter((proposal) => proposal.id !== proposalId);
}

export function defaultProposalName(createdAt: string, sequenceNumber: number) {
  const formatted = formatProposalDate(createdAt);
  return `Förslag ${sequenceNumber} · ${formatted}`;
}

export function formatProposalDate(createdAt: string) {
  return new Intl.DateTimeFormat("sv-SE", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit"
  }).format(new Date(createdAt));
}

function summarizeProposal(solution: SolveResponse): SavedProposalSummary {
  return {
    status: solution.status,
    objective_value: solution.objective_value,
    group_count: solution.assignments.length,
    requested_partner_satisfied: solution.summary?.requested_partner_satisfied ?? 0,
    requested_partner_total: solution.summary?.requested_partner_total ?? 0,
    preferred_period_satisfied: solution.summary?.preferred_period_satisfied ?? 0,
    preferred_period_total: solution.summary?.preferred_period_total ?? 0,
    exact_quota_group_count: solution.summary?.exact_quota_group_count ?? 0,
    total_group_count: solution.summary?.group_count ?? 0
  };
}
