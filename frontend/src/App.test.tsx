import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, test, vi } from "vitest";

vi.mock("./api", () => ({
  describeApiError: (error: unknown) =>
    error instanceof Error ? `UI:${error.message}` : "UI:Unexpected error",
  exportGroupsCsv: vi.fn(),
  fetchWorkspace: vi.fn(),
  fetchExampleScenario: vi.fn(),
  importBlockedPairsCsv: vi.fn(),
  importMentorsCsv: vi.fn(),
  importScenarioJson: vi.fn(),
  saveWorkspace: vi.fn(),
  solveScenario: vi.fn(),
  validateScenario: vi.fn()
}));

import App from "./App";
import { fetchWorkspace, saveWorkspace, solveScenario, validateScenario } from "./api";
import { createEmptyScenario } from "./types";

const mockedFetchWorkspace = vi.mocked(fetchWorkspace);
const mockedSaveWorkspace = vi.mocked(saveWorkspace);
const mockedValidateScenario = vi.mocked(validateScenario);
const mockedSolveScenario = vi.mocked(solveScenario);

function buildSolvedResponse() {
  return {
    status: "feasible" as const,
    objective_value: 1234,
    warnings: [],
    errors: [],
    assignments: [],
    summary: {
      mentor_count: 0,
      group_count: 20,
      total_assignments: 0,
      international_group_count: 2,
      blocked_pair_count: 0,
      blocked_pair_violations: 0,
      one_period_assignment_violations: 0,
      two_period_assignment_violations: 0,
      leader_assignment_violations: 0,
      leader_role_violations: 0,
      leader_group_role_violations: 0,
      nonpreferred_international_repeat_violations: 0,
      event_absolute_violations: 0,
      exact_quota_group_count: 20,
      quota_deviation_group_count: 0,
      preferred_international_satisfied: 0,
      preferred_international_total: 0,
      nonpreferred_international_assignments: 0,
      requested_partner_satisfied: 0,
      requested_partner_total: 0,
      preferred_period_satisfied: 0,
      preferred_period_total: 0,
      repeated_groupmate_pair_count: 0
    },
    score: {
      components: [],
      grouped_penalties: {},
      total_penalty: 0
    },
    report: {
      overview: [],
      hard_constraint_statuses: [],
      soft_goal_statuses: [],
      compromises: [],
      diagnostics: [],
      quota_deviations: [],
      request_outcomes: [],
      preferred_period_misses: [],
      repeated_groupmates: [],
      distributions: [],
      metadata: {}
    },
    solver_stats: {}
  };
}

describe("App", () => {
  beforeEach(() => {
    vi.resetAllMocks();
    mockedFetchWorkspace.mockResolvedValue({ scenario: createEmptyScenario(), saved_proposals: [] });
    mockedSaveWorkspace.mockImplementation(async (payload) => payload);
  });

  test("shows a clear startup error when sample loading fails", async () => {
    mockedFetchWorkspace.mockRejectedValue(new Error("backend unavailable"));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Startar med ett tomt scenario.")).toBeTruthy();
    });
    expect(screen.getByText("UI:backend unavailable")).toBeTruthy();
    expect(screen.getByText("TRULS")).toBeTruthy();
  });

  test("shows a clear solve error when the solve request fails", async () => {
    mockedValidateScenario.mockResolvedValue({
      ok: true,
      errors: [],
      warnings: [],
      summary: {
        mentor_count: 0,
        blocked_pair_count: 0,
        normal_one_period_supply: 0,
        normal_one_period_target: 0,
        normal_two_period_supply: 0,
        normal_two_period_target: 0,
        sexi_supply: 0,
        leader_supply: 0,
        leader_target: 0,
        event_assignment_supply: 0,
        event_ideal_capacity: 0,
        event_absolute_capacity: 0,
        international_preference_count: 0
      }
    });
    mockedSolveScenario.mockRejectedValue(new Error("solve failed"));

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Arbetsyta laddades.")).toBeTruthy();
    });

    await userEvent.click(screen.getByRole("button", { name: "Grupper" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Generera nytt förslag" })[0]);

    await waitFor(() => {
      expect(screen.getByText("UI:solve failed")).toBeTruthy();
    });
  });

  test("saves a generated proposal to local history", async () => {
    mockedValidateScenario.mockResolvedValue({
      ok: true,
      errors: [],
      warnings: [],
      summary: {
        mentor_count: 0,
        blocked_pair_count: 0,
        normal_one_period_supply: 0,
        normal_one_period_target: 0,
        normal_two_period_supply: 0,
        normal_two_period_target: 0,
        sexi_supply: 0,
        leader_supply: 0,
        leader_target: 0,
        event_assignment_supply: 0,
        event_ideal_capacity: 0,
        event_absolute_capacity: 0,
        international_preference_count: 0
      }
    });
    mockedSolveScenario.mockResolvedValue(buildSolvedResponse());

    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Arbetsyta laddades.")).toBeTruthy();
    });

    await userEvent.click(screen.getByRole("button", { name: "Grupper" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Generera nytt förslag" })[0]);

    await waitFor(() => {
      expect(screen.getByText("Aktuellt förslag")).toBeTruthy();
    });

    await userEvent.click(screen.getByRole("button", { name: "Spara aktuellt förslag" }));

    await waitFor(() => {
      expect(screen.getByText(/Sparade förslaget som/)).toBeTruthy();
    });
    expect(screen.getAllByText("Sparade förslag").length).toBeGreaterThan(0);
  });

  test("saves scenario changes explicitly from the data section", async () => {
    render(<App />);

    await waitFor(() => {
      expect(screen.getByText("Arbetsyta laddades.")).toBeTruthy();
    });

    await userEvent.click(screen.getByRole("button", { name: "Mentorer (0)" }));
    await userEvent.click(screen.getByRole("button", { name: "Lägg till mentor" }));
    await userEvent.click(screen.getAllByRole("button", { name: "Spara ändringar" })[0]);

    await waitFor(() => {
      expect(screen.getByText("Ändringarna i data och inställningar sparades.")).toBeTruthy();
    });
    expect(mockedSaveWorkspace).toHaveBeenCalled();
  });
});
