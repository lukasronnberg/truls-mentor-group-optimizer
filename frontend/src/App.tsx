import { useEffect, useMemo, useRef, useState, type ChangeEvent } from "react";

import {
  describeApiError,
  exportGroupsCsv,
  fetchExampleScenario,
  fetchWorkspace,
  importBlockedPairsCsv,
  importMentorsCsv,
  importScenarioJson,
  saveWorkspace,
  solveScenario,
  validateScenario
} from "./api";
import {
  buildProposalRecord,
  deleteProposal,
  formatProposalDate,
  renameProposal
} from "./proposals";
import {
  createBlankBlockedPair,
  createBlankMentor,
  createEmptyScenario,
  type AssignedMentor,
  type BlockedPair,
  type DistributionSeries,
  type GroupResult,
  type Mentor,
  type SavedProposal,
  type ScenarioInput,
  type ScenarioIssue,
  type SolveResponse,
  type ValidationResponse
} from "./types";

type MainSection = "data" | "groups" | "settings";
type DataSection = "overview" | "mentors" | "blocked" | "quality";
type GroupDashboardTab = "groups" | "compromises" | "statistics" | "advanced";
type PeriodNumber = 1 | 2;
type IndicatorTone = "neutral" | "warning" | "alert" | "info" | "good";

const WEIGHT_GROUPS: Array<{
  title: string;
  description: string;
  tone?: "priority";
  fields: Array<{
    key: keyof ScenarioInput["weights"];
    label: string;
    help: string;
  }>;
}> = [
  {
    title: "Prioriteringar i förslaget",
    description: "De här styr vad TRULS offrar först när allt inte går att få samtidigt.",
    tone: "priority",
    fields: [
      {
        key: "request_missing",
        label: "Prioritera önskade personer starkt",
        help: "Det här ska väga mycket tungt. Höj för att TRULS nästan alltid ska välja en lösning där varje mentor får minst en önskad person i varje period."
      },
      {
        key: "preferred_period_miss",
        label: "Rätt period för enperiodsmentorer",
        help: "Höj om periodönskemål ska vägas tyngre för mentors who only participate one period."
      },
      {
        key: "repeated_groupmates",
        label: "Minska upprepade personer mellan perioder",
        help: "Lägre prioritet. TRULS straffar främst overlap utöver en återkommande person, så detta ska inte slå ut önskade personer."
      }
    ]
  },
  {
    title: "Internationella grupper och kvoter",
    description: "Hur hårt kvoter och internationella önskemål ska försvaras.",
    fields: [
      {
        key: "quota_shortfall",
        label: "Underskott mot gruppkvot",
        help: "Hög vikt betyder att TRULS väldigt ogärna lämnar en grupp under kvot."
      },
      {
        key: "quota_overflow",
        label: "Överskott mot gruppkvot",
        help: "Används när strikt kvot måste släppas för att få en genomförbar lösning."
      },
      {
        key: "international_extra_two_period_shortfall",
        label: "Internationella extra platser med tvåperiodare",
        help: "Höj om de tre extra platserna i internationell grupp helst ska tas av tvåperiodsmentorer."
      },
      {
        key: "nonpreferred_international",
        label: "Skicka någon till intis utan önskemål",
        help: "Höj om TRULS ska vara mer försiktig med att placera normalmentorer i intis utan önskemål."
      }
    ]
  },
  {
    title: "Balans och spridning",
    description: "Finjustering av spridning när kärnkraven redan är uppfyllda.",
    fields: [
      {
        key: "event_second_mentor",
        label: "Två eventmentorer i samma grupp",
        help: "Höj om du vill undvika att event koncentreras i samma grupp."
      },
      {
        key: "event_evenness",
        label: "Jämn spridning av event",
        help: "Höj om eventmentorer ska spridas jämnare över grupperna."
      },
      {
        key: "sexi_evenness",
        label: "Håll sexi mycket jämnt fördelade",
        help: "TRULS minimerar nu maxlast, spridning och överbelastning. Använd denna om du vill försvara målet att ingen grupp ska sticka iväg långt över resten."
      },
      {
        key: "balance_gender",
        label: "Jämn könsfördelning",
        help: "Höj om könsbalans ska väga tyngre när TRULS väljer mellan flera likvärdiga lösningar."
      },
      {
        key: "balance_year",
        label: "Jämn årskursfördelning",
        help: "Höj om årskurser ska blandas jämnare."
      }
    ]
  }
];

function App() {
  const [scenario, setScenario] = useState<ScenarioInput>(createEmptyScenario());
  const [validation, setValidation] = useState<ValidationResponse | null>(null);
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");
  const [isBusy, setIsBusy] = useState(false);

  const [mainSection, setMainSection] = useState<MainSection>("data");
  const [dataSection, setDataSection] = useState<DataSection>("overview");
  const [groupDashboardTab, setGroupDashboardTab] = useState<GroupDashboardTab>("groups");
  const [activePeriod, setActivePeriod] = useState<PeriodNumber>(1);
  const [mentorFilter, setMentorFilter] = useState("");
  const [currentProposal, setCurrentProposal] = useState<SavedProposal | null>(null);
  const [savedProposals, setSavedProposals] = useState<SavedProposal[]>([]);
  const [selectedProposalId, setSelectedProposalId] = useState<string | "current" | null>("current");
  const [shouldFocusGroups, setShouldFocusGroups] = useState(false);
  const [isScenarioDirty, setIsScenarioDirty] = useState(false);

  const scenarioFileRef = useRef<HTMLInputElement | null>(null);
  const mentorCsvRef = useRef<HTMLInputElement | null>(null);
  const blockedCsvRef = useRef<HTMLInputElement | null>(null);
  const groupsHeaderRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    document.title = "TRULS";
  }, []);

  useEffect(() => {
    fetchWorkspace()
      .then((workspace) => {
        setScenario(workspace.scenario);
        setSavedProposals(workspace.saved_proposals ?? []);
        setMessage(
          workspace.saved_proposals?.length
            ? "Arbetsyta laddades med sparade förslag."
            : "Arbetsyta laddades."
        );
        setIsScenarioDirty(false);
      })
      .catch((caughtError) => {
        setError(describeApiError(caughtError));
        setMessage("Startar med ett tomt scenario.");
      });
  }, []);

  useEffect(() => {
    if (!currentProposal && savedProposals.length > 0 && selectedProposalId === "current") {
      setSelectedProposalId(savedProposals[0].id);
    }
  }, [currentProposal, savedProposals, selectedProposalId]);

  useEffect(() => {
    if (!shouldFocusGroups) {
      return;
    }
    window.requestAnimationFrame(() => {
      groupsHeaderRef.current?.focus({ preventScroll: true });
      if (typeof groupsHeaderRef.current?.scrollIntoView === "function") {
        groupsHeaderRef.current.scrollIntoView({ behavior: "smooth", block: "start" });
      }
    });
    setShouldFocusGroups(false);
  }, [shouldFocusGroups]);

  const activeProposal = useMemo(() => {
    if (selectedProposalId === "current") {
      return currentProposal;
    }
    return savedProposals.find((proposal) => proposal.id === selectedProposalId) ?? currentProposal;
  }, [currentProposal, savedProposals, selectedProposalId]);

  const mentorIds = useMemo(
    () => [...new Set(scenario.mentors.map((mentor) => mentor.id))].sort(),
    [scenario.mentors]
  );

  const filteredMentors = useMemo(() => {
    const normalizedFilter = mentorFilter.trim().toLowerCase();
    return scenario.mentors
      .map((mentor, index) => ({ mentor, index }))
      .filter(({ mentor }) => {
        if (!normalizedFilter) {
          return true;
        }
        return (
          mentor.id.toLowerCase().includes(normalizedFilter) ||
          mentor.name.toLowerCase().includes(normalizedFilter) ||
          mentor.category.toLowerCase().includes(normalizedFilter) ||
          mentor.gender.toLowerCase().includes(normalizedFilter) ||
          mentor.year.toLowerCase().includes(normalizedFilter) ||
          (mentor.normal_subrole ?? "").toLowerCase().includes(normalizedFilter)
        );
      });
  }, [mentorFilter, scenario.mentors]);

  const scenarioStats = useMemo(() => buildScenarioStats(scenario), [scenario]);
  const activeWarnings = activeProposal?.solution.warnings ?? validation?.warnings ?? [];
  const activeErrors = activeProposal?.solution.errors ?? validation?.errors ?? [];
  const proposalSummary = useMemo(
    () => (activeProposal ? buildCompromiseSummary(activeProposal.solution) : null),
    [activeProposal]
  );
  const activeGroupsByPeriod = useMemo(
    () => ({
      1: activeProposal?.solution.assignments.filter((group) => group.period === 1) ?? [],
      2: activeProposal?.solution.assignments.filter((group) => group.period === 2) ?? []
    }),
    [activeProposal]
  );

  function clearStatus() {
    setMessage("");
    setError("");
  }

  function markScenarioChanged(nextScenario: ScenarioInput | ((current: ScenarioInput) => ScenarioInput)) {
    clearStatus();
    setValidation(null);
    setIsScenarioDirty(true);
    setScenario((current) =>
      typeof nextScenario === "function"
        ? (nextScenario as (current: ScenarioInput) => ScenarioInput)(current)
        : nextScenario
    );
  }

  async function persistWorkspaceState(
    nextScenario: ScenarioInput,
    nextSavedProposals: SavedProposal[],
    successMessage?: string
  ) {
    const workspace = await saveWorkspace({
      scenario: cloneJson(nextScenario),
      saved_proposals: cloneJson(nextSavedProposals)
    });
    setScenario(workspace.scenario);
    setSavedProposals(workspace.saved_proposals);
    setIsScenarioDirty(false);
    if (successMessage) {
      setMessage(successMessage);
    }
  }

  function updateMentor(index: number, patch: Partial<Mentor>) {
    markScenarioChanged((current) => ({
      ...current,
      mentors: current.mentors.map((mentor, mentorIndex) =>
        mentorIndex === index ? { ...mentor, ...patch } : mentor
      )
    }));
  }

  function updateBlockedPair(index: number, patch: Partial<BlockedPair>) {
    markScenarioChanged((current) => ({
      ...current,
      blocked_pairs: current.blocked_pairs.map((pair, pairIndex) =>
        pairIndex === index ? { ...pair, ...patch } : pair
      )
    }));
  }

  function handleSettingChange(
    key: keyof ScenarioInput["settings"],
    value: number | boolean | Record<number, number>
  ) {
    markScenarioChanged((current) => ({
      ...current,
      settings: {
        ...current.settings,
        [key]: value
      }
    }));
  }

  function handleWeightChange(key: keyof ScenarioInput["weights"], value: number) {
    markScenarioChanged((current) => ({
      ...current,
      weights: {
        ...current.weights,
        [key]: value
      }
    }));
  }

  async function runAction(action: () => Promise<void>) {
    clearStatus();
    setIsBusy(true);
    try {
      await action();
    } catch (caughtError) {
      setError(describeApiError(caughtError));
    } finally {
      setIsBusy(false);
    }
  }

  async function handleLoadSample() {
    await runAction(async () => {
      const data = await fetchExampleScenario();
      setScenario(data);
      setValidation(null);
      setIsScenarioDirty(true);
      setDataSection("overview");
      setMainSection("data");
      setMessage("Standarddata laddades. Spara ändringarna om du vill behålla dem nästa gång.");
    });
  }

  async function handleSaveChanges() {
    await runAction(async () => {
      await persistWorkspaceState(scenario, savedProposals, "Ändringarna i data och inställningar sparades.");
    });
  }

  async function handleValidate() {
    await runAction(async () => {
      const result = await validateScenario(scenario);
      setValidation(result);
      setMainSection("data");
      setDataSection("quality");
      setMessage(
        result.ok
          ? `Datakontroll klar med ${result.warnings.length} varning(ar).`
          : `Datakontroll hittade ${result.errors.length} blockerande problem.`
      );
    });
  }

  async function handleGenerateProposal() {
    await runAction(async () => {
      const validationResult = await validateScenario(scenario);
      setValidation(validationResult);
      if (!validationResult.ok) {
        setMainSection("data");
        setDataSection("quality");
        setError("Lös de blockerande dataproblemen innan TRULS genererar ett nytt förslag.");
        return;
      }

      const result = await solveScenario(scenario);
      const proposal = buildProposalRecord(
        cloneJson(scenario),
        cloneJson(validationResult),
        cloneJson(result),
        savedProposals.length + 1
      );
      setCurrentProposal(proposal);
      setSelectedProposalId("current");
      setMainSection("groups");
      setGroupDashboardTab("groups");
      setActivePeriod(1);
      setShouldFocusGroups(true);
      setMessage(`TRULS genererade ett nytt förslag med status ${result.status}.`);
    });
  }

  async function handleSaveCurrentProposal() {
    if (!currentProposal) {
      setError("Generera ett förslag innan du sparar.");
      return;
    }
    await runAction(async () => {
      const proposalToSave = buildProposalRecord(
        cloneJson(currentProposal.scenario),
        cloneJson(currentProposal.validation),
        cloneJson(currentProposal.solution),
        savedProposals.length + 1,
        currentProposal.name
      );
      await persistWorkspaceState(
        scenario,
        [proposalToSave, ...savedProposals],
        `Sparade förslaget som “${proposalToSave.name}”.`
      );
    });
  }

  async function handleRenameSavedProposal(proposal: SavedProposal) {
    const nextName = window.prompt("Nytt namn på förslaget", proposal.name);
    if (!nextName) {
      return;
    }
    await runAction(async () => {
      const nextSavedProposals = renameProposal(savedProposals, proposal.id, nextName);
      await persistWorkspaceState(scenario, nextSavedProposals, `Bytte namn på “${proposal.name}”.`);
    });
  }

  async function handleDeleteSavedProposal(proposal: SavedProposal) {
    if (!window.confirm(`Ta bort “${proposal.name}”?`)) {
      return;
    }
    await runAction(async () => {
      const nextSavedProposals = deleteProposal(savedProposals, proposal.id);
      await persistWorkspaceState(scenario, nextSavedProposals, `Tog bort “${proposal.name}”.`);
      if (selectedProposalId === proposal.id) {
        setSelectedProposalId(currentProposal ? "current" : null);
      }
    });
  }

  function handleExportScenarioJson() {
    const blob = new Blob([JSON.stringify(scenario, null, 2)], { type: "application/json" });
    downloadBlob(blob, "truls-scenario.json");
    setMessage("Scenario exporterades som JSON.");
  }

  async function handleExportGroupsCsv() {
    if (!activeProposal) {
      setError("Öppna eller generera ett förslag först.");
      return;
    }
    await runAction(async () => {
      const blob = await exportGroupsCsv(activeProposal.solution);
      downloadBlob(blob, "truls-grupper.csv");
      setMessage("Grupper exporterades som CSV.");
    });
  }

  async function handleScenarioImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await runAction(async () => {
      const imported = await importScenarioJson(file);
      setScenario(imported);
      setValidation(null);
      setIsScenarioDirty(true);
      setMainSection("data");
      setDataSection("overview");
      setMessage(`Importerade scenario från ${file.name}. Spara ändringarna om du vill behålla dem nästa gång.`);
      event.target.value = "";
    });
  }

  async function handleMentorCsvImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await runAction(async () => {
      const mentors = await importMentorsCsv(file);
      markScenarioChanged((current) => ({ ...current, mentors }));
      setMainSection("data");
      setDataSection("mentors");
      setMessage(`Importerade ${mentors.length} mentorer från ${file.name}.`);
      event.target.value = "";
    });
  }

  async function handleBlockedCsvImport(event: ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) {
      return;
    }
    await runAction(async () => {
      const blockedPairs = await importBlockedPairsCsv(file);
      markScenarioChanged((current) => ({ ...current, blocked_pairs: blockedPairs }));
      setMainSection("data");
      setDataSection("blocked");
      setMessage(`Importerade ${blockedPairs.length} spärrade par från ${file.name}.`);
      event.target.value = "";
    });
  }

  function handleAddMentor() {
    markScenarioChanged((current) => ({
      ...current,
      mentors: [...current.mentors, createBlankMentor(current.mentors.length + 1)]
    }));
    setDataSection("mentors");
  }

  function handleRemoveMentor(index: number) {
    markScenarioChanged((current) => ({
      ...current,
      mentors: current.mentors.filter((_, mentorIndex) => mentorIndex !== index)
    }));
  }

  function handleAddBlockedPair() {
    markScenarioChanged((current) => ({
      ...current,
      blocked_pairs: [...current.blocked_pairs, createBlankBlockedPair()]
    }));
    setDataSection("blocked");
  }

  function handleRemoveBlockedPair(index: number) {
    markScenarioChanged((current) => ({
      ...current,
      blocked_pairs: current.blocked_pairs.filter((_, pairIndex) => pairIndex !== index)
    }));
  }

  return (
    <div className="app-shell">
      <datalist id="mentor-id-options">
        {mentorIds.map((mentorId) => (
          <option key={mentorId} value={mentorId} />
        ))}
      </datalist>

      <header className="brand-shell panel">
        <div className="brand-copy">
          <p className="eyebrow">Robot för gruppförslag</p>
          <h1>TRULS</h1>
          <p className="brand-tagline">
            Förbered data, generera gruppförslag och jämför sparade upplägg i ett lokalt planeringssystem.
          </p>
        </div>
        <nav className="main-nav" aria-label="Main">
          {[
            { key: "data", label: "Data" },
            { key: "groups", label: "Grupper" },
            { key: "settings", label: "Inställningar" }
          ].map((item) => (
            <button
              key={item.key}
              type="button"
              className={`main-nav-button ${mainSection === item.key ? "active" : ""}`}
              onClick={() => setMainSection(item.key as MainSection)}
            >
              {item.label}
            </button>
          ))}
        </nav>
        <div className="top-metrics">
          <MetricBox label="Mentorer" value={scenario.mentors.length} />
          <MetricBox label="Sparade förslag" value={savedProposals.length} />
          <MetricBox label="Ändringar" value={isScenarioDirty ? "Ej sparat" : "Sparat"} tone={isScenarioDirty ? "warning" : "good"} />
          <MetricBox
            label="Aktiv vy"
            value={mainSection === "groups" ? "Grupper" : mainSection === "data" ? "Data" : "Inställningar"}
            tone="info"
          />
        </div>
      </header>

      {message && <section className="banner success">{message}</section>}
      {error && <section className="banner error">{error}</section>}

      {mainSection === "data" && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Data</p>
              <h2>Förbered underlaget</h2>
              <p>Här laddar du in filer, redigerar mentorer, hanterar spärrade par och granskar datakvalitet.</p>
            </div>
            <div className="action-row">
              <button type="button" className="primary" onClick={handleSaveChanges} disabled={isBusy || !isScenarioDirty}>
                Spara ändringar
              </button>
              <button type="button" onClick={handleLoadSample} disabled={isBusy}>
                Ladda standarddata
              </button>
              <button type="button" onClick={handleValidate} disabled={isBusy}>
                Kontrollera data
              </button>
              <button type="button" onClick={() => scenarioFileRef.current?.click()} disabled={isBusy}>
                Importera JSON
              </button>
              <button type="button" onClick={() => mentorCsvRef.current?.click()} disabled={isBusy}>
                Importera mentorer
              </button>
              <button type="button" onClick={() => blockedCsvRef.current?.click()} disabled={isBusy}>
                Importera spärrade par
              </button>
              <button type="button" onClick={handleExportScenarioJson} disabled={isBusy}>
                Exportera scenario
              </button>
            </div>
          </div>

          <SegmentedTabs
            value={dataSection}
            onChange={(value) => setDataSection(value as DataSection)}
            options={[
              { value: "overview", label: "Översikt" },
              { value: "mentors", label: `Mentorer (${scenario.mentors.length})` },
              { value: "blocked", label: `Spärrade par (${scenario.blocked_pairs.length})` },
              { value: "quality", label: "Datakvalitet" }
            ]}
          />

          {dataSection === "overview" && (
            <DataOverview scenario={scenario} scenarioStats={scenarioStats} validation={validation} />
          )}
          {dataSection === "mentors" && (
            <MentorEditor
              mentors={filteredMentors}
              mentorFilter={mentorFilter}
              setMentorFilter={setMentorFilter}
              onAddMentor={handleAddMentor}
              onRemoveMentor={handleRemoveMentor}
              updateMentor={updateMentor}
            />
          )}
          {dataSection === "blocked" && (
            <BlockedPairsEditor
              pairs={scenario.blocked_pairs}
              onAddBlockedPair={handleAddBlockedPair}
              onRemoveBlockedPair={handleRemoveBlockedPair}
              updateBlockedPair={updateBlockedPair}
            />
          )}
          {dataSection === "quality" && (
            <DataQualityPanel validation={validation} warnings={activeWarnings} errors={activeErrors} />
          )}

          <input ref={scenarioFileRef} hidden type="file" accept=".json" onChange={handleScenarioImport} />
          <input ref={mentorCsvRef} hidden type="file" accept=".csv" onChange={handleMentorCsvImport} />
          <input ref={blockedCsvRef} hidden type="file" accept=".csv" onChange={handleBlockedCsvImport} />
        </section>
      )}

      {mainSection === "groups" && (
        <section className="panel groups-shell">
          <div ref={groupsHeaderRef} tabIndex={-1} className="panel-header groups-header">
            <div>
              <p className="section-kicker">Grupper</p>
              <h2>Förslag och historik</h2>
              <p>Generera nya förslag med TRULS, jämför tidigare sparade varianter och granska detaljer när det behövs.</p>
            </div>
            <div className="action-row">
              <button type="button" className="primary" onClick={handleGenerateProposal} disabled={isBusy}>
                Generera nytt förslag
              </button>
              <button type="button" onClick={handleSaveCurrentProposal} disabled={isBusy || !currentProposal}>
                Spara aktuellt förslag
              </button>
              <button type="button" onClick={handleExportGroupsCsv} disabled={isBusy || !activeProposal}>
                Exportera grupper
              </button>
              {currentProposal && selectedProposalId !== "current" && (
                <button type="button" onClick={() => setSelectedProposalId("current")}>
                  Visa aktuellt
                </button>
              )}
            </div>
          </div>

          <div className="groups-layout">
            <aside className="proposal-sidebar subpanel">
              <div className="subpanel-header">
                <div>
                  <h3>Förslagshistorik</h3>
                  <p>Sparade förslag ligger kvar lokalt även efter att du stänger appen.</p>
                </div>
              </div>

              <div className="proposal-stack">
                <ProposalCard
                  title="Aktuellt förslag"
                  proposal={currentProposal}
                  active={selectedProposalId === "current"}
                  badge="AKTUELLT"
                  emptyLabel="Inget nytt förslag har genererats ännu."
                  onOpen={() => setSelectedProposalId("current")}
                />

                <div className="proposal-section-label">Sparade förslag</div>
                {savedProposals.length ? (
                  savedProposals.map((proposal) => (
                    <ProposalCard
                      key={proposal.id}
                      title={proposal.name}
                      proposal={proposal}
                      active={selectedProposalId === proposal.id}
                      badge="SPARAT"
                      onOpen={() => setSelectedProposalId(proposal.id)}
                      onRename={() => handleRenameSavedProposal(proposal)}
                      onDelete={() => handleDeleteSavedProposal(proposal)}
                    />
                  ))
                ) : (
                  <div className="proposal-empty">Inga sparade förslag ännu.</div>
                )}
              </div>
            </aside>

            <div className="proposal-main">
              {activeProposal && proposalSummary ? (
                <>
                  <section className="subpanel proposal-overview">
                    <div className="subpanel-header">
                      <div>
                        <h3>{selectedProposalId === "current" ? "Aktivt förslag" : activeProposal.name}</h3>
                        <p>
                          {selectedProposalId === "current" ? "Senast genererat av TRULS" : "Öppnat från lokal historik"} ·{" "}
                          {formatProposalDate(activeProposal.created_at)}
                        </p>
                      </div>
                    </div>
                    <div className="summary-strip">
                      <MetricBox label="Status" value={activeProposal.solution.status} tone="good" />
                      <MetricBox
                        label="Önskad person uppfyllt"
                        value={`${activeProposal.summary.requested_partner_satisfied}/${activeProposal.summary.requested_partner_total}`}
                        tone="info"
                      />
                      <MetricBox
                        label="Rätt period"
                        value={`${activeProposal.summary.preferred_period_satisfied}/${activeProposal.summary.preferred_period_total}`}
                      />
                      <MetricBox
                        label="Exakta kvotgrupper"
                        value={`${activeProposal.summary.exact_quota_group_count}/${activeProposal.summary.total_group_count}`}
                      />
                      <MetricBox label="Signalproblem" value={proposalSummary.totalCompromiseCount} tone="warning" />
                    </div>
                  </section>

                  <SegmentedTabs
                    value={groupDashboardTab}
                    onChange={(value) => setGroupDashboardTab(value as GroupDashboardTab)}
                    options={[
                      { value: "groups", label: "Gruppvy" },
                      { value: "compromises", label: `Kompromisser (${proposalSummary.totalCompromiseCount})` },
                      { value: "statistics", label: "Statistik" },
                      { value: "advanced", label: "Avancerat" }
                    ]}
                  />

                  {groupDashboardTab === "groups" && (
                    <GroupsView
                      activePeriod={activePeriod}
                      setActivePeriod={setActivePeriod}
                      groups={activeGroupsByPeriod}
                      summary={proposalSummary}
                    />
                  )}
                  {groupDashboardTab === "compromises" && (
                    <CompromisesView
                      proposal={activeProposal}
                      summary={proposalSummary}
                      warnings={activeWarnings}
                      errors={activeErrors}
                    />
                  )}
                  {groupDashboardTab === "statistics" && (
                    <StatisticsView proposal={activeProposal} summary={proposalSummary} groups={activeGroupsByPeriod} />
                  )}
                  {groupDashboardTab === "advanced" && (
                    <AdvancedView
                      proposal={activeProposal}
                      validation={activeProposal.validation}
                      warnings={activeWarnings}
                      errors={activeErrors}
                    />
                  )}
                </>
              ) : (
                <section className="subpanel empty-proposal">
                  <h3>Inget förslag öppet</h3>
                  <p>
                    Gå igenom datan och låt sedan TRULS generera ett nytt förslag. Sparade förslag kommer också att visas
                    här.
                  </p>
                  <button type="button" className="primary" onClick={handleGenerateProposal} disabled={isBusy}>
                    Generera nytt förslag
                  </button>
                </section>
              )}
            </div>
          </div>
        </section>
      )}

      {mainSection === "settings" && (
        <section className="panel">
          <div className="panel-header">
            <div>
              <p className="section-kicker">Inställningar</p>
              <h2>Styr hur TRULS tänker</h2>
              <p>Gruppmodell och prioriteringar presenteras i organiserade sektioner i stället för en teknisk siffervägg.</p>
            </div>
            <div className="action-row">
              <button type="button" className="primary" onClick={handleSaveChanges} disabled={isBusy || !isScenarioDirty}>
                Spara ändringar
              </button>
            </div>
          </div>

          <div className="settings-grid">
            <section className="subpanel emphasis">
              <div className="subpanel-header">
                <div>
                  <h3>Viktigaste prioritet just nu</h3>
                  <p>Standardläget har ändrats så att minst en önskad person väger tydligt tyngre än att undvika upprepning.</p>
                </div>
              </div>
              <div className="priority-callout">
                <div>
                  <strong>Önskad person i gruppen</strong>
                  <span>{scenario.weights.request_missing}</span>
                </div>
                <div>
                  <strong>Jämn sexi-spridning</strong>
                  <span>{scenario.weights.sexi_evenness}</span>
                </div>
                <div>
                  <strong>Upprepad overlap mellan perioder</strong>
                  <span>{scenario.weights.repeated_groupmates}</span>
                </div>
              </div>
              <p className="muted-copy">
                Repeated overlap straffas nu mildare, och främst när någon får fler än en upprepad gruppkamrat mellan perioderna. Sexi sprids samtidigt med hårdare balanslogik.
              </p>
            </section>

            <section className="subpanel">
              <div className="subpanel-header">
                <div>
                  <h3>Gruppmodell</h3>
                  <p>Praktiska grundinställningar för hur grupperna ska byggas.</p>
                </div>
              </div>
              <div className="field-grid compact">
                <NumberField
                  label="Grupper per period"
                  value={scenario.settings.groups_per_period}
                  onChange={(value) => handleSettingChange("groups_per_period", value)}
                />
                <NumberField
                  label="Enperiodsmentorer per grupp"
                  value={scenario.settings.regular_group_quota_one_period}
                  onChange={(value) => handleSettingChange("regular_group_quota_one_period", value)}
                />
                <NumberField
                  label="Tvåperiodsmentorer per grupp"
                  value={scenario.settings.regular_group_quota_two_period}
                  onChange={(value) => handleSettingChange("regular_group_quota_two_period", value)}
                />
                <NumberField
                  label="Extra normalmentorer i intis"
                  value={scenario.settings.international_extra_mentors}
                  onChange={(value) => handleSettingChange("international_extra_mentors", value)}
                />
                <NumberField
                  label="Intisgrupp i period 1"
                  value={scenario.settings.international_group_numbers[1]}
                  onChange={(value) =>
                    handleSettingChange("international_group_numbers", {
                      ...scenario.settings.international_group_numbers,
                      1: value
                    })
                  }
                />
                <NumberField
                  label="Intisgrupp i period 2"
                  value={scenario.settings.international_group_numbers[2]}
                  onChange={(value) =>
                    handleSettingChange("international_group_numbers", {
                      ...scenario.settings.international_group_numbers,
                      2: value
                    })
                  }
                />
                <NumberField
                  label="Max önskat antal event / grupp"
                  value={scenario.settings.ideal_max_event_mentors_per_group}
                  onChange={(value) => handleSettingChange("ideal_max_event_mentors_per_group", value)}
                />
                <NumberField
                  label="Absolut max event / grupp"
                  value={scenario.settings.absolute_max_event_mentors_per_group}
                  onChange={(value) => handleSettingChange("absolute_max_event_mentors_per_group", value)}
                />
                <NumberField
                  label="Max lösningstid (sek)"
                  value={scenario.settings.max_solver_time_seconds}
                  onChange={(value) => handleSettingChange("max_solver_time_seconds", value)}
                />
              </div>
              <label className="checkbox-row">
                <input
                  type="checkbox"
                  checked={scenario.settings.enforce_strict_quotas_when_feasible}
                  onChange={(event) => handleSettingChange("enforce_strict_quotas_when_feasible", event.target.checked)}
                />
                <span>Börja med strikt kvotmodell och släpp först när det behövs för att hitta en möjlig lösning.</span>
              </label>
            </section>

            {WEIGHT_GROUPS.map((group) => (
              <section key={group.title} className={`subpanel ${group.tone === "priority" ? "priority-panel" : ""}`}>
                <div className="subpanel-header">
                  <div>
                    <h3>{group.title}</h3>
                    <p>{group.description}</p>
                  </div>
                </div>
                <div className="setting-stack">
                  {group.fields.map((field) => (
                    <SettingRow
                      key={field.key}
                      label={field.label}
                      help={field.help}
                      value={scenario.weights[field.key]}
                      onChange={(value) => handleWeightChange(field.key, value)}
                    />
                  ))}
                </div>
              </section>
            ))}
          </div>
        </section>
      )}
    </div>
  );
}

function DataOverview({
  scenario,
  scenarioStats,
  validation
}: {
  scenario: ScenarioInput;
  scenarioStats: ReturnType<typeof buildScenarioStats>;
  validation: ValidationResponse | null;
}) {
  return (
    <div className="data-overview-grid">
      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Scenarioöversikt</h3>
            <p>Snabb blick över vad som finns i underlaget just nu.</p>
          </div>
        </div>
        <div className="summary-strip">
          <MetricBox label="Normal" value={scenarioStats.normal} />
          <MetricBox label="Enperiod" value={scenarioStats.normalOnePeriod} />
          <MetricBox label="Tvåperiod" value={scenarioStats.normalTwoPeriod} />
          <MetricBox label="Sexi" value={scenarioStats.sexi} />
          <MetricBox label="Hövdingar" value={scenarioStats.leaders} />
          <MetricBox label="Event" value={scenarioStats.event} />
          <MetricBox label="Intis-önskemål" value={scenarioStats.international} />
        </div>
      </section>

      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Nuvarande gruppmodell</h3>
            <p>Det här är ramen TRULS arbetar inom när ett nytt förslag genereras.</p>
          </div>
        </div>
        <ul className="plain-list">
          <li>{scenario.settings.groups_per_period} grupper per period.</li>
          <li>{scenario.settings.regular_group_quota_one_period} enperiods-normalmentorer per grupp.</li>
          <li>{scenario.settings.regular_group_quota_two_period} tvåperiods-normalmentorer per grupp.</li>
          <li>{scenario.settings.international_extra_mentors} extra normalmentorer i varje internationell grupp.</li>
          <li>Intisgrupp: period 1 grupp {scenario.settings.international_group_numbers[1]}, period 2 grupp {scenario.settings.international_group_numbers[2]}.</li>
        </ul>
      </section>

      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Datakvalitet</h3>
            <p>Senaste kända läge från validering.</p>
          </div>
        </div>
        {validation ? (
          <div className="summary-strip">
            <MetricBox label="Blockerande fel" value={validation.errors.length} tone={validation.errors.length ? "warning" : "good"} />
            <MetricBox label="Varningar" value={validation.warnings.length} tone={validation.warnings.length ? "warning" : "good"} />
            <MetricBox
              label="Normal enperiod"
              value={`${validation.summary.normal_one_period_supply}/${validation.summary.normal_one_period_target}`}
            />
            <MetricBox
              label="Normal tvåperiod"
              value={`${validation.summary.normal_two_period_supply}/${validation.summary.normal_two_period_target}`}
            />
            <MetricBox
              label="Hövdingar"
              value={`${validation.summary.leader_supply}/${validation.summary.leader_target}`}
            />
          </div>
        ) : (
          <p className="muted-copy">Ingen datakontroll körd ännu. Gå till Datakvalitet för att granska underlaget.</p>
        )}
      </section>
    </div>
  );
}

function DataQualityPanel({
  validation,
  warnings,
  errors
}: {
  validation: ValidationResponse | null;
  warnings: ScenarioIssue[];
  errors: ScenarioIssue[];
}) {
  return (
    <div className="data-overview-grid">
      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Sammanfattning</h3>
            <p>Blockerande fel stoppar TRULS från att generera ett nytt förslag.</p>
          </div>
        </div>
        {validation ? (
          <div className="summary-strip">
            <MetricBox label="Mentorer" value={validation.summary.mentor_count} />
            <MetricBox label="Spärrade par" value={validation.summary.blocked_pair_count} />
            <MetricBox label="Fel" value={errors.length} tone={errors.length ? "warning" : "good"} />
            <MetricBox label="Varningar" value={warnings.length} tone={warnings.length ? "warning" : "good"} />
          </div>
        ) : (
          <p className="muted-copy">Kör “Kontrollera data” för att se valideringsresultat här.</p>
        )}
      </section>

      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Blockerande fel</h3>
          </div>
        </div>
        <IssueList issues={errors} emptyLabel="Inga blockerande fel." variant="error" />
      </section>

      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Varningar</h3>
          </div>
        </div>
        <IssueList issues={warnings} emptyLabel="Inga varningar." variant="warning" />
      </section>
    </div>
  );
}

function MentorEditor({
  mentors,
  mentorFilter,
  setMentorFilter,
  onAddMentor,
  onRemoveMentor,
  updateMentor
}: {
  mentors: Array<{ mentor: Mentor; index: number }>;
  mentorFilter: string;
  setMentorFilter: (value: string) => void;
  onAddMentor: () => void;
  onRemoveMentor: (index: number) => void;
  updateMentor: (index: number, patch: Partial<Mentor>) => void;
}) {
  return (
    <section className="subpanel">
      <div className="subpanel-header">
        <div>
          <h3>Mentorer</h3>
          <p>Filtrera och redigera roster i en kompakt tabell utan att sidan växer okontrollerat.</p>
        </div>
        <div className="inline-actions">
          <input
            className="filter-input"
            placeholder="Filtrera på namn, id, kategori, kön, år"
            value={mentorFilter}
            onChange={(event) => setMentorFilter(event.target.value)}
          />
          <button type="button" onClick={onAddMentor}>
            Lägg till mentor
          </button>
        </div>
      </div>
      <div className="table-wrap tall">
        <table className="editor-table">
          <thead>
            <tr>
              <th>ID</th>
              <th>Namn</th>
              <th>Kategori</th>
              <th>Deltar</th>
              <th>Önskad period</th>
              <th>Kön</th>
              <th>År</th>
              <th>Subroll</th>
              <th>Önskade personer</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {mentors.map(({ mentor, index }) => (
              <tr key={`${mentor.id}-${index}`}>
                <td>
                  <input value={mentor.id} onChange={(event) => updateMentor(index, { id: event.target.value })} />
                </td>
                <td>
                  <input value={mentor.name} onChange={(event) => updateMentor(index, { name: event.target.value })} />
                </td>
                <td>
                  <select
                    value={mentor.category}
                    onChange={(event) => {
                      const category = event.target.value as Mentor["category"];
                      updateMentor(index, {
                        category,
                        normal_subrole: category === "normal" ? mentor.normal_subrole ?? "normal" : null,
                        participation: category === "hovding" ? "two_period" : mentor.participation,
                        preferred_period:
                          category === "hovding"
                            ? null
                            : mentor.participation === "one_period"
                              ? mentor.preferred_period ?? 1
                              : null
                      });
                    }}
                  >
                    <option value="normal">normal</option>
                    <option value="sexi">sexi</option>
                    <option value="hovding">hovding</option>
                  </select>
                </td>
                <td>
                  <select
                    value={mentor.participation}
                    disabled={mentor.category === "hovding"}
                    onChange={(event) =>
                      updateMentor(index, {
                        participation: event.target.value as Mentor["participation"],
                        preferred_period: event.target.value === "two_period" ? null : mentor.preferred_period ?? 1
                      })
                    }
                  >
                    <option value="one_period">one_period</option>
                    <option value="two_period">two_period</option>
                  </select>
                </td>
                <td>
                  {mentor.participation === "one_period" ? (
                    <select
                      value={mentor.preferred_period ?? 1}
                      onChange={(event) => updateMentor(index, { preferred_period: Number(event.target.value) })}
                    >
                      <option value={1}>1</option>
                      <option value={2}>2</option>
                    </select>
                  ) : (
                    <span className="muted-copy">n/a</span>
                  )}
                </td>
                <td>
                  <input value={mentor.gender} onChange={(event) => updateMentor(index, { gender: event.target.value })} />
                </td>
                <td>
                  <input value={mentor.year} onChange={(event) => updateMentor(index, { year: event.target.value })} />
                </td>
                <td>
                  {mentor.category === "normal" ? (
                    <select
                      value={mentor.normal_subrole ?? "normal"}
                      onChange={(event) =>
                        updateMentor(index, { normal_subrole: event.target.value as Mentor["normal_subrole"] })
                      }
                    >
                      <option value="normal">normal</option>
                      <option value="event">event</option>
                      <option value="international">international</option>
                    </select>
                  ) : (
                    <span className="muted-copy">n/a</span>
                  )}
                </td>
                <td>
                  <input
                    list="mentor-id-options"
                    placeholder="M001, M002"
                    value={mentor.requested_with.join(", ")}
                    onChange={(event) =>
                      updateMentor(index, {
                        requested_with: event.target.value
                          .split(",")
                          .map((value) => value.trim())
                          .filter(Boolean)
                          .slice(0, 3)
                      })
                    }
                  />
                </td>
                <td>
                  <button type="button" className="ghost" onClick={() => onRemoveMentor(index)}>
                    Ta bort
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function BlockedPairsEditor({
  pairs,
  onAddBlockedPair,
  onRemoveBlockedPair,
  updateBlockedPair
}: {
  pairs: BlockedPair[];
  onAddBlockedPair: () => void;
  onRemoveBlockedPair: (index: number) => void;
  updateBlockedPair: (index: number, patch: Partial<BlockedPair>) => void;
}) {
  return (
    <section className="subpanel">
      <div className="subpanel-header">
        <div>
          <h3>Spärrade par</h3>
          <p>Mentorer som aldrig får hamna i samma grupp.</p>
        </div>
        <button type="button" onClick={onAddBlockedPair}>
          Lägg till spärrat par
        </button>
      </div>
      <div className="table-wrap medium">
        <table className="editor-table compact-width">
          <thead>
            <tr>
              <th>Mentor A</th>
              <th>Mentor B</th>
              <th></th>
            </tr>
          </thead>
          <tbody>
            {pairs.map((pair, index) => (
              <tr key={`${pair.mentor_a}-${pair.mentor_b}-${index}`}>
                <td>
                  <input
                    list="mentor-id-options"
                    value={pair.mentor_a}
                    onChange={(event) => updateBlockedPair(index, { mentor_a: event.target.value })}
                  />
                </td>
                <td>
                  <input
                    list="mentor-id-options"
                    value={pair.mentor_b}
                    onChange={(event) => updateBlockedPair(index, { mentor_b: event.target.value })}
                  />
                </td>
                <td>
                  <button type="button" className="ghost" onClick={() => onRemoveBlockedPair(index)}>
                    Ta bort
                  </button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function ProposalCard({
  title,
  proposal,
  active,
  badge,
  emptyLabel,
  onOpen,
  onRename,
  onDelete
}: {
  title: string;
  proposal: SavedProposal | null;
  active: boolean;
  badge: string;
  emptyLabel?: string;
  onOpen?: () => void;
  onRename?: () => void;
  onDelete?: () => void;
}) {
  if (!proposal) {
    return <div className="proposal-empty">{emptyLabel ?? "Ingen data."}</div>;
  }
  return (
    <div className={`proposal-card ${active ? "active" : ""}`}>
      <div className="proposal-card-header">
        <div>
          <p className="proposal-badge">{badge}</p>
          <strong>{title}</strong>
        </div>
        {active && <span className="indicator good">visas nu</span>}
      </div>
      <p className="proposal-date">{formatProposalDate(proposal.created_at)}</p>
      <div className="proposal-metrics">
        <span>{proposal.summary.status}</span>
        <span>
          önskad {proposal.summary.requested_partner_satisfied}/{proposal.summary.requested_partner_total}
        </span>
        <span>
          kvot {proposal.summary.exact_quota_group_count}/{proposal.summary.total_group_count}
        </span>
      </div>
      <div className="proposal-actions">
        {onOpen && (
          <button type="button" onClick={onOpen}>
            Öppna
          </button>
        )}
        {onRename && (
          <button type="button" onClick={onRename}>
            Byt namn
          </button>
        )}
        {onDelete && (
          <button type="button" className="danger" onClick={onDelete}>
            Ta bort
          </button>
        )}
      </div>
    </div>
  );
}

function GroupsView({
  activePeriod,
  setActivePeriod,
  groups,
  summary
}: {
  activePeriod: PeriodNumber;
  setActivePeriod: (period: PeriodNumber) => void;
  groups: Record<PeriodNumber, GroupResult[]>;
  summary: ReturnType<typeof buildCompromiseSummary>;
}) {
  const visibleGroups = groups[activePeriod];

  return (
    <div className="dashboard-body">
      <div className="dashboard-toolbar">
        <SegmentedTabs
          value={String(activePeriod)}
          onChange={(value) => setActivePeriod(Number(value) as PeriodNumber)}
          options={[
            { value: "1", label: `Period 1 (${groups[1].length})` },
            { value: "2", label: `Period 2 (${groups[2].length})` }
          ]}
        />
        <div className="status-row compact">
          <StatusChip
            label="Önskad person uppfylld"
            value={`${summary.requestSatisfaction[activePeriod].satisfied}/${summary.requestSatisfaction[activePeriod].total}`}
            tone="good"
          />
          <StatusChip label="Utan önskad person" value={summary.requestMisses[activePeriod].length} tone="warning" />
          <StatusChip label="Fel period" value={summary.preferredMisses[activePeriod].length} tone="warning" />
          <StatusChip label="Intis utan önskemål" value={summary.nonPreferredInternational[activePeriod].length} tone="info" />
          <StatusChip
            label="Sexi min/max"
            value={`${summary.sexiDistribution[activePeriod].min}-${summary.sexiDistribution[activePeriod].max}`}
            tone={summary.sexiDistribution[activePeriod].withinTarget ? "good" : "alert"}
          />
        </div>
      </div>
      <div className="group-grid">
        {visibleGroups.map((group) => (
          <GroupCard key={`${group.period}-${group.group_number}`} group={group} summary={summary} />
        ))}
      </div>
    </div>
  );
}

function GroupCard({
  group,
  summary
}: {
  group: GroupResult;
  summary: ReturnType<typeof buildCompromiseSummary>;
}) {
  const head = group.mentors.find((mentor) => mentor.assigned_leader_role === "head") ?? null;
  const vice = group.mentors.find((mentor) => mentor.assigned_leader_role === "vice") ?? null;
  const roster = group.mentors.filter((mentor) => mentor.assigned_leader_role === null);
  const groupKey = `${group.period}-${group.group_number}`;
  const quotaAdjusted = summary.quotaAdjustedGroups.has(groupKey);
  const eventConcentration = group.summary.event_count > 1;
  const flaggedPeople = roster.filter((mentor) => getMentorIndicators(group, mentor, summary).length > 0).length;

  return (
    <article className={`group-card ${group.is_international ? "international" : ""}`}>
      <header className="group-card-header">
        <div className="group-card-topline">
          <div>
            <h3>{group.label}</h3>
            <p>
              Normal {group.summary.normal_total_count} · Sexi {group.summary.sexi_count} · Event {group.summary.event_count}
            </p>
          </div>
          <div className="group-badges">
            {group.is_international && <Indicator label="Intis" tone="info" />}
            {quotaAdjusted && <Indicator label="Kvot justerad" tone="warning" />}
            {eventConcentration && <Indicator label="Eventkluster" tone="warning" />}
            {flaggedPeople > 0 && <Indicator label={`${flaggedPeople} flaggade placeringar`} tone="alert" />}
          </div>
        </div>

        <div className="leader-strip">
          <div className="leader-box head">
            <span>Head</span>
            <strong>{head?.name ?? "Saknas"}</strong>
          </div>
          <div className="leader-box vice">
            <span>Vice</span>
            <strong>{vice?.name ?? "Saknas"}</strong>
          </div>
        </div>

        <div className="distribution-lines">
          <span>Kön: {formatBreakdown(group.summary.gender_breakdown, "gender")}</span>
          <span>År: {formatBreakdown(group.summary.year_breakdown, "year")}</span>
        </div>
      </header>

      <div className="mentor-grid">
        {roster.map((mentor) => {
          const indicators = getMentorIndicators(group, mentor, summary);
          return (
            <div key={mentor.id} className={`mentor-tile ${indicators.length ? "flagged" : ""}`}>
              <div className="mentor-tile-header">
                <strong>{mentor.name}</strong>
                <span className="mentor-meta">{formatMentorMeta(mentor)}</span>
              </div>
              {indicators.length > 0 && (
                <div className="indicator-row">
                  {indicators.map((indicator) => (
                    <Indicator key={`${mentor.id}-${indicator.label}`} label={indicator.label} tone={indicator.tone} />
                  ))}
                </div>
              )}
            </div>
          );
        })}
      </div>
    </article>
  );
}

function CompromisesView({
  proposal,
  summary,
  warnings,
  errors
}: {
  proposal: SavedProposal;
  summary: ReturnType<typeof buildCompromiseSummary>;
  warnings: ScenarioIssue[];
  errors: ScenarioIssue[];
}) {
  return (
    <div className="accordion-stack">
      <CompromiseFoldout
        title={`Ingen önskad person – period 1 (${summary.requestMisses[1].length})`}
        entries={summary.requestMisses[1]}
        emptyLabel="Alla fick minst en önskad person i period 1."
        open={summary.requestMisses[1].length > 0}
      />
      <CompromiseFoldout
        title={`Ingen önskad person – period 2 (${summary.requestMisses[2].length})`}
        entries={summary.requestMisses[2]}
        emptyLabel="Alla fick minst en önskad person i period 2."
      />
      <CompromiseFoldout
        title={`Fel period för enperiodsmentor (${summary.preferredMisses[1].length + summary.preferredMisses[2].length})`}
        entries={[
          ...summary.preferredMisses[1].map((entry) => `${entry} → placerad i period 1`),
          ...summary.preferredMisses[2].map((entry) => `${entry} → placerad i period 2`)
        ]}
        emptyLabel="Alla enperiodsmentorer fick sin önskade period."
      />
      <CompromiseFoldout
        title={`Intisplacering utan önskemål (${summary.nonPreferredInternational[1].length + summary.nonPreferredInternational[2].length})`}
        entries={[
          ...summary.nonPreferredInternational[1].map((entry) => `${entry} → period 1`),
          ...summary.nonPreferredInternational[2].map((entry) => `${entry} → period 2`)
        ]}
        emptyLabel="Inga extra intisplaceringar utan önskemål behövdes."
      />
      <CompromiseFoldout
        title={`Sexi-spridning (${summary.sexiAlerts.length})`}
        entries={summary.sexiAlerts}
        emptyLabel="Sexi låg inom målbandet i båda perioderna."
        open={summary.sexiAlerts.length > 0}
      />
      <CompromiseFoldout
        title={`Upprepade gruppkamrater (${summary.repeatedGroupmates.length})`}
        entries={summary.repeatedGroupmates.map(
          (item) => `${item.mentor_name}: ${item.repeated_groupmate_count} upprepade (${item.repeated_with.join(", ")})`
        )}
        emptyLabel="Ingen tvåperiodsmentor fick problematisk upprepad overlap."
      />
      <CompromiseFoldout
        title={`Grupper med eventkoncentration (${summary.eventConcentration.length})`}
        entries={summary.eventConcentration}
        emptyLabel="Ingen grupp fick mer än en eventmentor."
      />
      <CompromiseFoldout
        title={`Grupper där kvoten fick justeras (${summary.quotaAdjustedDetails.length})`}
        entries={summary.quotaAdjustedDetails}
        emptyLabel="Alla grupper träffade exakt kvotmodell."
      />
      <details className="foldout">
        <summary>Regelstatus</summary>
        <div className="foldout-body rule-columns">
          <section>
            <h4>Hårda regler</h4>
            <RuleList rules={proposal.solution.report?.hard_constraint_statuses ?? []} />
          </section>
          <section>
            <h4>Mjukare mål</h4>
            <RuleList rules={proposal.solution.report?.soft_goal_statuses ?? []} />
          </section>
        </div>
      </details>
      <details className="foldout">
        <summary>Varningar och fel ({warnings.length + errors.length})</summary>
        <div className="foldout-body rule-columns">
          <section>
            <h4>Fel</h4>
            <IssueList issues={errors} emptyLabel="Inga fel." variant="error" />
          </section>
          <section>
            <h4>Varningar</h4>
            <IssueList issues={warnings} emptyLabel="Inga varningar." variant="warning" />
          </section>
        </div>
      </details>
    </div>
  );
}

function StatisticsView({
  proposal,
  summary,
  groups
}: {
  proposal: SavedProposal;
  summary: ReturnType<typeof buildCompromiseSummary>;
  groups: Record<PeriodNumber, GroupResult[]>;
}) {
  const distributions = groupDistributionsByCategory(proposal.solution.report?.distributions ?? []);
  return (
    <div className="stats-layout">
      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Nyckeltal</h3>
            <p>De viktigaste värdena för att snabbt bedöma kvaliteten i förslaget.</p>
          </div>
        </div>
        <div className="summary-strip">
          <MetricBox label="Status" value={proposal.solution.status} tone="good" />
          <MetricBox
            label="Önskad person"
            value={`${proposal.summary.requested_partner_satisfied}/${proposal.summary.requested_partner_total}`}
            tone="info"
          />
          <MetricBox
            label="Period 1 önskemål"
            value={`${summary.requestSatisfaction[1].satisfied}/${summary.requestSatisfaction[1].total}`}
            tone="good"
          />
          <MetricBox
            label="Period 2 önskemål"
            value={`${summary.requestSatisfaction[2].satisfied}/${summary.requestSatisfaction[2].total}`}
            tone="good"
          />
          <MetricBox
            label="Rätt period"
            value={`${proposal.summary.preferred_period_satisfied}/${proposal.summary.preferred_period_total}`}
          />
          <MetricBox label="Upprepad overlap" value={summary.repeatedGroupmates.length} tone="warning" />
        </div>
      </section>

      <section className="subpanel">
        <div className="subpanel-header">
          <div>
            <h3>Periodöversikt</h3>
            <p>Snabb driftbild för respektive period.</p>
          </div>
        </div>
        <div className="period-snapshot-grid">
          {[1, 2].map((period) => (
            <div key={period} className="period-snapshot-card">
              <h4>Period {period}</h4>
              <p>Grupper: {groups[period as PeriodNumber].length}</p>
              <p>Intisgrupper: {groups[period as PeriodNumber].filter((group) => group.is_international).length}</p>
              <p>Event totalt: {groups[period as PeriodNumber].reduce((sum, group) => sum + group.summary.event_count, 0)}</p>
              <p>Sexi totalt: {groups[period as PeriodNumber].reduce((sum, group) => sum + group.summary.sexi_count, 0)}</p>
              <p>
                Sexi min/max: {summary.sexiDistribution[period as PeriodNumber].min}/
                {summary.sexiDistribution[period as PeriodNumber].max}
              </p>
              <p>Utan önskad person: {summary.requestMisses[period as PeriodNumber].length}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="subpanel full-span">
        <div className="subpanel-header">
          <div>
            <h3>Spridningssammanfattning</h3>
            <p>Läsbar fördelning per kategori, utan att öppna råa tekniska tabeller.</p>
          </div>
        </div>
        <div className="accordion-stack">
          {Object.entries(distributions).map(([category, entries]) => (
            <details key={category} className="foldout">
              <summary>{toTitleCase(category)}</summary>
              <div className="foldout-body">
                <ul className="plain-list">
                  {entries.map((entry) => (
                    <li key={`${entry.category}-${entry.value}`}>
                      <strong>{entry.value}</strong>: total range {entry.overall_min_count}-{entry.overall_max_count}
                      {" · "}
                      P1 [{entry.per_period.find((item) => item.period === 1)?.counts_by_group.join(" / ") ?? "-"}]
                      {" · "}
                      P2 [{entry.per_period.find((item) => item.period === 2)?.counts_by_group.join(" / ") ?? "-"}]
                    </li>
                  ))}
                </ul>
              </div>
            </details>
          ))}
        </div>
      </section>
    </div>
  );
}

function AdvancedView({
  proposal,
  validation,
  warnings,
  errors
}: {
  proposal: SavedProposal;
  validation: ValidationResponse | null;
  warnings: ScenarioIssue[];
  errors: ScenarioIssue[];
}) {
  return (
    <div className="accordion-stack">
      <details className="foldout" open>
        <summary>Optimeringsdetaljer</summary>
        <div className="foldout-body">
          <div className="summary-strip">
            <MetricBox label="Objective" value={proposal.solution.objective_value ?? "n/a"} />
            <MetricBox label="Quota mode" value={String(proposal.solution.solver_stats.quota_mode ?? "unknown")} />
            <MetricBox label="Solver status" value={String(proposal.solution.solver_stats.status_name ?? "unknown")} />
            <MetricBox label="Wall time (s)" value={String(proposal.solution.solver_stats.wall_time_seconds ?? "n/a")} />
            <MetricBox label="Branches" value={String(proposal.solution.solver_stats.branches ?? "n/a")} />
          </div>
        </div>
      </details>
      <details className="foldout">
        <summary>Viktad score breakdown</summary>
        <div className="foldout-body">
          {proposal.solution.score ? (
            <>
              <div className="summary-strip">
                {Object.entries(proposal.solution.score.grouped_penalties).map(([key, value]) => (
                  <MetricBox key={key} label={key} value={value} />
                ))}
                <MetricBox label="Total" value={proposal.solution.score.total_penalty} tone="warning" />
              </div>
              <div className="table-wrap medium">
                <table className="editor-table compact-width">
                  <thead>
                    <tr>
                      <th>Komponent</th>
                      <th>Kategori</th>
                      <th>Vikt</th>
                      <th>Råvärde</th>
                      <th>Penalty</th>
                    </tr>
                  </thead>
                  <tbody>
                    {proposal.solution.score.components.map((component) => (
                      <tr key={component.key}>
                        <td>{component.label}</td>
                        <td>{component.category}</td>
                        <td>{component.weight}</td>
                        <td>{component.raw_value}</td>
                        <td>{component.weighted_penalty}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </>
          ) : (
            <p className="muted-copy">Ingen score breakdown tillgänglig.</p>
          )}
        </div>
      </details>
      <details className="foldout">
        <summary>Metadata och diagnostik</summary>
        <div className="foldout-body rule-columns">
          <section>
            <h4>Metadata</h4>
            <ul className="plain-list">
              {Object.entries(proposal.solution.report?.metadata ?? {}).map(([key, value]) => (
                <li key={key}>
                  <strong>{key}</strong>: {String(value)}
                </li>
              ))}
              {Object.keys(proposal.solution.report?.metadata ?? {}).length === 0 && <li>Ingen metadata rapporterad.</li>}
            </ul>
            {proposal.solution.report?.diagnostics?.length ? (
              <>
                <h4>Diagnostics</h4>
                <ul className="plain-list">
                  {proposal.solution.report.diagnostics.map((entry) => (
                    <li key={entry}>{entry}</li>
                  ))}
                </ul>
              </>
            ) : null}
          </section>
          <section>
            <h4>Valideringsläge</h4>
            <p className="muted-copy">
              {validation ? `Validation ok: ${validation.ok ? "ja" : "nej"}` : "Ingen aktuell validering i minnet."}
            </p>
            <IssueList issues={errors} emptyLabel="Inga fel." variant="error" />
            <IssueList issues={warnings} emptyLabel="Inga varningar." variant="warning" />
          </section>
        </div>
      </details>
    </div>
  );
}

function MetricBox({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "good" | "warning" | "info";
}) {
  return (
    <div className={`metric-box ${tone}`}>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusChip({
  label,
  value,
  tone = "neutral"
}: {
  label: string;
  value: string | number;
  tone?: IndicatorTone;
}) {
  return (
    <span className={`status-chip ${tone}`}>
      <strong>{value}</strong>
      <span>{label}</span>
    </span>
  );
}

function Indicator({ label, tone }: { label: string; tone: IndicatorTone }) {
  return <span className={`indicator ${tone}`}>{label}</span>;
}

function SegmentedTabs({
  value,
  onChange,
  options
}: {
  value: string;
  onChange: (value: string) => void;
  options: Array<{ value: string; label: string }>;
}) {
  return (
    <div className="segmented-tabs" role="tablist">
      {options.map((option) => (
        <button
          key={option.value}
          type="button"
          className={`tab-button ${value === option.value ? "active" : ""}`}
          onClick={() => onChange(option.value)}
        >
          {option.label}
        </button>
      ))}
    </div>
  );
}

function SettingRow({
  label,
  help,
  value,
  onChange
}: {
  label: string;
  help: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label className="setting-row">
      <div>
        <strong>{label}</strong>
        <p>{help}</p>
      </div>
      <input type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function NumberField({
  label,
  value,
  onChange
}: {
  label: string;
  value: number;
  onChange: (value: number) => void;
}) {
  return (
    <label>
      <span>{label}</span>
      <input type="number" value={value} onChange={(event) => onChange(Number(event.target.value))} />
    </label>
  );
}

function CompromiseFoldout({
  title,
  entries,
  emptyLabel,
  open = false
}: {
  title: string;
  entries: string[];
  emptyLabel: string;
  open?: boolean;
}) {
  return (
    <details className="foldout" open={open}>
      <summary>{title}</summary>
      <div className="foldout-body">
        <ul className="plain-list">
          {entries.length ? entries.map((entry) => <li key={entry}>{entry}</li>) : <li>{emptyLabel}</li>}
        </ul>
      </div>
    </details>
  );
}

function RuleList({ rules }: { rules: Array<{ title: string; status: string; summary: string; details: string[] }> }) {
  return (
    <ul className="plain-list rule-list">
      {rules.length ? (
        rules.map((rule) => (
          <li key={rule.title}>
            <div className="rule-line">
              <strong>{rule.title}</strong>
              <Indicator
                label={rule.status.replace(/_/g, " ")}
                tone={rule.status === "violated" ? "alert" : rule.status === "partially_satisfied" ? "warning" : "info"}
              />
            </div>
            <div className="muted-copy">{rule.summary}</div>
            {rule.details.length > 0 && <div className="micro-copy">{rule.details.join(" ")}</div>}
          </li>
        ))
      ) : (
        <li>Inga regelbedömningar.</li>
      )}
    </ul>
  );
}

function IssueList({
  issues,
  emptyLabel,
  variant
}: {
  issues: ScenarioIssue[];
  emptyLabel: string;
  variant: "warning" | "error";
}) {
  return (
    <ul className={`plain-list issue-list ${variant}`}>
      {issues.length ? (
        issues.map((issue) => (
          <li key={`${issue.code}-${issue.message}`}>
            <strong>{issue.message}</strong>
            {issue.details && <div className="micro-copy">{issue.details}</div>}
          </li>
        ))
      ) : (
        <li>{emptyLabel}</li>
      )}
    </ul>
  );
}

function buildScenarioStats(scenario: ScenarioInput) {
  return {
    normal: scenario.mentors.filter((mentor) => mentor.category === "normal").length,
    normalOnePeriod: scenario.mentors.filter(
      (mentor) => mentor.category === "normal" && mentor.participation === "one_period"
    ).length,
    normalTwoPeriod: scenario.mentors.filter(
      (mentor) => mentor.category === "normal" && mentor.participation === "two_period"
    ).length,
    sexi: scenario.mentors.filter((mentor) => mentor.category === "sexi").length,
    leaders: scenario.mentors.filter((mentor) => mentor.category === "hovding").length,
    event: scenario.mentors.filter((mentor) => mentor.normal_subrole === "event").length,
    international: scenario.mentors.filter((mentor) => mentor.normal_subrole === "international").length
  };
}

function buildCompromiseSummary(solution: SolveResponse) {
  const requestMisses: Record<PeriodNumber, string[]> = { 1: [], 2: [] };
  const preferredMisses: Record<PeriodNumber, string[]> = { 1: [], 2: [] };
  const nonPreferredInternational: Record<PeriodNumber, string[]> = { 1: [], 2: [] };
  const requestSatisfaction: Record<PeriodNumber, { satisfied: number; total: number }> = {
    1: { satisfied: 0, total: 0 },
    2: { satisfied: 0, total: 0 }
  };
  const requestMissSet: Record<PeriodNumber, Set<string>> = { 1: new Set(), 2: new Set() };
  const preferredMissSet: Record<PeriodNumber, Set<string>> = { 1: new Set(), 2: new Set() };
  const intlSet: Record<PeriodNumber, Set<string>> = { 1: new Set(), 2: new Set() };

  for (const outcome of solution.report?.request_outcomes ?? []) {
    const period = outcome.period as PeriodNumber;
    requestSatisfaction[period].total += 1;
    if (outcome.satisfied) {
      requestSatisfaction[period].satisfied += 1;
    }
    if (!outcome.satisfied && !requestMissSet[period].has(outcome.mentor_name)) {
      requestMissSet[period].add(outcome.mentor_name);
      requestMisses[period].push(outcome.mentor_name);
    }
  }

  for (const miss of solution.report?.preferred_period_misses ?? []) {
    const period = miss.assigned_period as PeriodNumber;
    const label = `${miss.mentor_name} (ville ${miss.preferred_period})`;
    if (!preferredMissSet[period].has(label)) {
      preferredMissSet[period].add(label);
      preferredMisses[period].push(label);
    }
  }

  for (const group of solution.assignments) {
    if (!group.is_international) {
      continue;
    }
    for (const mentor of group.mentors) {
      if (mentor.category !== "normal" || mentor.normal_subrole === "international") {
        continue;
      }
      const period = group.period as PeriodNumber;
      if (!intlSet[period].has(mentor.name)) {
        intlSet[period].add(mentor.name);
        nonPreferredInternational[period].push(mentor.name);
      }
    }
  }

  const repeatedGroupmates = (solution.report?.repeated_groupmates ?? [])
    .filter((item) => item.repeated_groupmate_count > 0)
    .sort((left, right) => right.repeated_groupmate_count - left.repeated_groupmate_count);

  const quotaAdjustedDetails = (solution.report?.quota_deviations ?? [])
    .filter(
      (item) =>
        item.actual_total_normal_count !== item.target_total_normal_count ||
        item.actual_normal_one_period_count !== item.target_normal_one_period_baseline ||
        item.actual_normal_two_period_count !== item.target_normal_two_period_baseline
    )
    .map(
      (item) =>
        `${item.label}: totalt ${item.actual_total_normal_count}/${item.target_total_normal_count}, enperiod ${item.actual_normal_one_period_count}/${item.target_normal_one_period_baseline}, tvåperiod ${item.actual_normal_two_period_count}/${item.target_normal_two_period_baseline}`
    );

  const eventConcentration = solution.assignments
    .filter((group) => group.summary.event_count > 1)
    .map((group) => `${group.label}: ${group.summary.event_count} eventmentorer`);

  const sexiDistribution = ([1, 2] as PeriodNumber[]).reduce<
    Record<PeriodNumber, { counts: number[]; min: number; max: number; range: number; withinTarget: boolean }>
  >(
    (accumulator, period) => {
      const counts = solution.assignments
        .filter((group) => group.period === period)
        .map((group) => group.summary.sexi_count);
      const min = counts.length ? Math.min(...counts) : 0;
      const max = counts.length ? Math.max(...counts) : 0;
      accumulator[period] = {
        counts,
        min,
        max,
        range: max - min,
        withinTarget: max <= 3 && max - min <= 2
      };
      return accumulator;
    },
    {
      1: { counts: [], min: 0, max: 0, range: 0, withinTarget: true },
      2: { counts: [], min: 0, max: 0, range: 0, withinTarget: true }
    }
  );

  const sexiAlerts = ([1, 2] as PeriodNumber[])
    .filter((period) => !sexiDistribution[period].withinTarget)
    .map(
      (period) =>
        `Period ${period}: sexi ${sexiDistribution[period].counts.join(" / ")} (min ${sexiDistribution[period].min}, max ${sexiDistribution[period].max})`
    );

  return {
    requestMisses,
    requestSatisfaction,
    preferredMisses,
    nonPreferredInternational,
    sexiDistribution,
    sexiAlerts,
    repeatedGroupmates,
    quotaAdjustedGroups: new Set(
      (solution.report?.quota_deviations ?? [])
        .filter(
          (item) =>
            item.actual_total_normal_count !== item.target_total_normal_count ||
            item.actual_normal_one_period_count !== item.target_normal_one_period_baseline ||
            item.actual_normal_two_period_count !== item.target_normal_two_period_baseline
        )
        .map((item) => `${item.period}-${item.group_number}`)
    ),
    quotaAdjustedDetails,
    eventConcentration,
    totalCompromiseCount:
      requestMisses[1].length +
      requestMisses[2].length +
      preferredMisses[1].length +
      preferredMisses[2].length +
      nonPreferredInternational[1].length +
      nonPreferredInternational[2].length +
      sexiAlerts.length +
      repeatedGroupmates.length +
      eventConcentration.length +
      quotaAdjustedDetails.length
  };
}

function getMentorIndicators(
  group: GroupResult,
  mentor: AssignedMentor,
  summary: ReturnType<typeof buildCompromiseSummary>
): Array<{ label: string; tone: IndicatorTone }> {
  const indicators: Array<{ label: string; tone: IndicatorTone }> = [];
  const period = group.period as PeriodNumber;

  if (summary.requestMisses[period].includes(mentor.name)) {
    indicators.push({ label: "Ingen önskad person", tone: "warning" });
  }
  if (summary.preferredMisses[period].some((entry) => entry.startsWith(mentor.name))) {
    indicators.push({ label: "Fel period", tone: "warning" });
  }
  if (
    group.is_international &&
    mentor.category === "normal" &&
    mentor.normal_subrole !== "international" &&
    summary.nonPreferredInternational[period].includes(mentor.name)
  ) {
    indicators.push({ label: "Intis utan önskemål", tone: "info" });
  }
  const repeated = summary.repeatedGroupmates.find((item) => item.mentor_id === mentor.id);
  if (repeated) {
    indicators.push({ label: `Upprepad overlap ${repeated.repeated_groupmate_count}`, tone: "alert" });
  }
  if (mentor.category === "sexi") {
    indicators.push({ label: "Sexi", tone: "neutral" });
  }
  if (mentor.normal_subrole === "event") {
    indicators.push({ label: "Event", tone: "neutral" });
  }
  return indicators;
}

function formatMentorMeta(mentor: AssignedMentor) {
  const parts = [
    mentor.category.replace("_", " "),
    mentor.participation.replace("_", " "),
    mentor.gender,
    mentor.year
  ];
  if (mentor.normal_subrole) {
    parts.push(mentor.normal_subrole);
  }
  return parts.filter(Boolean).join(" · ");
}

function formatBreakdown(breakdown: Record<string, number>, mode: "gender" | "year") {
  const entries = Object.entries(breakdown).filter(([, value]) => value > 0);
  if (!entries.length) {
    return "n/a";
  }
  return entries
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([key, value]) => `${mode === "gender" ? formatGenderKey(key) : key} ${value}`)
    .join(" · ");
}

function formatGenderKey(value: string) {
  const normalized = value.trim().toLowerCase();
  if (normalized === "m") {
    return "M";
  }
  if (normalized === "f") {
    return "F";
  }
  return toTitleCase(value);
}

function groupDistributionsByCategory(distributions: DistributionSeries[]) {
  return distributions.reduce<Record<string, DistributionSeries[]>>((accumulator, item) => {
    accumulator[item.category] = [...(accumulator[item.category] ?? []), item];
    return accumulator;
  }, {});
}

function toTitleCase(value: string) {
  return value
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function cloneJson<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}

function downloadBlob(blob: Blob, fileName: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = fileName;
  link.click();
  URL.revokeObjectURL(url);
}

export default App;
