# Mentor Group Optimizer

Local-first web application for generating mentor groups for 2 periods with FastAPI, OR-Tools CP-SAT, React, TypeScript, Pydantic, and pytest.

## Architecture

- `backend/app/models.py`: domain models, API schemas, validation contracts
- `backend/app/validation.py`: fatal errors and pre-solve warnings
- `backend/app/solver.py`: CP-SAT model and solve pipeline
- `backend/app/scoring.py`: weighted soft-goal definitions and score breakdown
- `backend/app/reporting.py`: human-readable compromise report
- `backend/app/import_export.py`: CSV/JSON import and CSV export
- `backend/app/main.py`: FastAPI endpoints
- `backend/app/launcher.py`: one-command launcher for production-like and dev workflows
- `frontend/src/App.tsx`: TRULS UI for editing data, saving workspace changes, solving, and viewing results
- `frontend/src/api.ts`: frontend API client, backend discovery, and error handling
- `backend/app/workspace_store.py`: local workspace persistence for saved data and saved proposals
- `examples/`: sample JSON and CSV scenarios
- `tests/`: backend tests

## Current Domain Model

Each mentor has:

- `category`: `normal`, `sexi`, or `hovding`
- `participation`: `one_period` or `two_period`
- `preferred_period`: only for `one_period`
- `gender`
- `year`
- `requested_with`: up to 3 mentor ids

Only `category=normal` may also have:

- `normal_subrole`: `normal`, `event`, or `international`

Interpretation:

- `normal_subrole=event` means event mentor
- `normal_subrole=international` means the mentor must be placed in the international group in every period they participate
- `sexi` mentors are additive and do not count toward the 10-person normal base
- `hovding` mentors are leaders and do not count toward the 10-person normal base

## Group Composition

Regular group, per period:

- 2 one-period normal mentors
- 5 two-period normal mentors
- any sexi mentors on top
- exactly 2 leaders on top:
  - 1 `head`
  - 1 `vice`

International group, per period:

- same normal base: `2 + 5`
- plus 3 extra normal mentors
- extras are preferably two-period normal mentors
- any sexi mentors on top
- exactly 2 leaders on top:
  - 1 `head`
  - 1 `vice`

## Solver Strategy

The solver uses one assignment variable per mentor / period / group, plus explicit leader-role variables for `head` and `vice`.

Hard constraints:

- blocked pairs never share a group in any period
- one-period mentors are assigned exactly once
- two-period mentors are assigned once in each period
- each group gets exactly 2 leaders, exactly 1 head, exactly 1 vice
- each leader appears in both periods
- each leader is head once and vice once
- `normal_subrole=international` mentors are hard-assigned to the international group in every period they participate
- non-international mentors may be assigned to an international group in at most one period
- event mentors have absolute max 2 per group

Quota handling:

- the solver first attempts a strict solve
- if strict normal-pool quotas are infeasible, it falls back to a relaxed model
- the relaxed model keeps hard constraints and minimizes quota deviation penalties

Soft goals:

- give each mentor at least one requested partner in each period they participate
- honor preferred periods for one-period normal mentors
- minimize repeated groupmates for two-period normal mentors
- minimize second event mentors in a group
- distribute sexi mentors evenly
- distribute event mentors evenly
- balance groups by gender and year
- prefer two-period normals for international extra slots

## Configurable Weights

All weights live in `ScenarioInput.weights`.

- `quota_shortfall`: penalty for missing normal quota counts
- `quota_overflow`: penalty for exceeding normal quota counts in relaxed mode
- `international_extra_two_period_shortfall`: penalty when international extras are not filled by two-period normal mentors
- `international_preference`: retained for compatibility, but international-marked mentors are now enforced as a hard rule
- `nonpreferred_international`: penalty for assigning a non-preferring mentor to an international group
- `request_missing`: penalty when a mentor gets no requested partner in a participated period
- `preferred_period_miss`: penalty when a one-period normal mentor misses preferred period
- `repeated_groupmates`: penalty for repeated normal two-period pairings across both periods
- `event_second_mentor`: penalty for placing a second event mentor in the same group
- `event_evenness`: penalty for uneven event distribution
- `sexi_evenness`: penalty for uneven sexi distribution
- `balance_gender`: penalty for uneven gender distribution
- `balance_year`: penalty for uneven year distribution

## Import Formats

### Mentors CSV

Required columns:

```csv
id,name,category,participation
```

Recommended full format:

```csv
id,name,category,participation,preferred_period,gender,year,normal_subrole,requested_with
ON01,Alice,normal,one_period,1,woman,1,international,TN001;TN002
TN001,Bob,normal,two_period,,man,2,event,ON01
SX01,Clara,sexi,one_period,2,woman,3,,
HV01,David,hovding,two_period,,man,leader,,
```

Rules:

- `category` must be `normal`, `sexi`, or `hovding`
- `participation` must be `one_period` or `two_period`
- `preferred_period` must be `1` or `2` for `one_period`
- `preferred_period` must be blank for `two_period`
- `normal_subrole` may only be set for `category=normal`
- `normal_subrole` should be `normal`, `event`, or `international`
- `requested_with` may contain up to 3 mentor ids separated by `;`

### Blocked Pairs CSV

```csv
mentor_a,mentor_b
TN001,TN003
HV01,TN004
```

### Scenario JSON

`ScenarioInput` shape:

```json
{
  "mentors": [],
  "blocked_pairs": [],
  "settings": {},
  "weights": {}
}
```

See [examples/demo_scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_scenario.json) for a complete example.

## API

### `GET /api/example`

Returns the default scenario used by the app. If `data_raw/converted/scenario.json` exists, that file is used; otherwise the bundled demo scenario is used.

### `GET /api/workspace`

Returns the locally saved TRULS workspace:

- `scenario`
- `saved_proposals`

If no workspace file exists yet, TRULS starts from the default scenario and an empty proposal list.

### `POST /api/workspace`

Saves the current TRULS workspace locally. This is used for:

- `Spara ändringar` in the Data and Inställningar sections
- saved proposal history in Grupper

The workspace is stored in `.truls/workspace.json`.

### `POST /api/validate`

Input: `ScenarioInput`

Returns:

- `ok`
- `errors`
- `warnings`
- `summary`

Validation summary currently includes:

- mentor count
- blocked pair count
- normal one-period supply vs target
- normal two-period supply vs target
- sexi supply
- leader supply vs target
- event demand vs capacity
- international preference count

### `POST /api/solve`

Input: `ScenarioInput`

Returns:

- `status`
- `objective_value`
- `warnings`
- `errors`
- `assignments`
- `summary`
- `score`
- `report`
- `solver_stats`

The compromise report includes:

- hard-constraint statuses
- soft-goal statuses
- quota deviations
- mentor-period request outcomes
- preferred-period misses
- repeated-groupmate summaries
- distribution summaries for sexi, event, gender, and year

### `POST /api/export/groups-csv`

Input: `SolveResponse`

Returns CSV with:

- period/group metadata
- mentor identity
- category
- participation
- gender
- year
- normal subrole
- assigned leader role

## Local Development Defaults

- The app default dataset comes from [data_raw/converted/scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/data_raw/converted/scenario.json) when available.
- If the converted bundle is missing, the fallback sample is [examples/demo_scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_scenario.json).
- In Vite dev mode, the frontend can connect in three ways:
  - through the Vite `/api` proxy
  - through an explicit `VITE_API_BASE_URL`
  - through automatic discovery of likely local backend ports `8000-8005`

## Demo Data

Generated sample files:

- [examples/demo_scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_scenario.json)
- [examples/demo_mentors.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_mentors.csv)
- [examples/demo_blocked_pairs.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_blocked_pairs.csv)
- [examples/tight_scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/examples/tight_scenario.json)
- [examples/tight_mentors.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/tight_mentors.csv)
- [examples/tight_blocked_pairs.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/tight_blocked_pairs.csv)

The demo data includes:

- one-period normal mentors
- two-period normal mentors
- event mentors
- international-preferring normal mentors
- sexi mentors
- 20 hovding leaders
- requested partners
- blocked pairs

## Local Run

Backend:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
uvicorn backend.app.main:app --reload
```

Frontend:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls/frontend
npm install
npm run dev
```

Frontend with explicit backend URL:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls/frontend
VITE_API_BASE_URL=http://127.0.0.1:8000 npm run dev
```

Single-command launch:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
source .venv/bin/activate
mentor-groups
```

Single-command dev launch:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
source .venv/bin/activate
mentor-groups-dev
```

Mac launcher file:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
./mentor-groups.command
```

Tests:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
.venv/bin/pytest
```

Frontend tests:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls/frontend
npm test
```

Frontend production build:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls/frontend
npm run build
```

Regenerate sample data:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
.venv/bin/python scripts/generate_seed_data.py
```

Sync edited converted CSV data back into the default scenario bundle:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
.venv/bin/python scripts/sync_converted_bundle.py
```

## Troubleshooting

### "Failed to fetch" in the frontend

Typical local-dev causes:

- the backend is not running
- the frontend is targeting the wrong backend port
- the Vite proxy is pointing at the wrong backend port
- the backend returned malformed JSON
- the backend crashed and the frontend only surfaced the failure generically

This project now hardens those paths by:

- supporting `VITE_API_BASE_URL`
- probing backend ports `8000-8005` in Vite dev mode
- returning structured JSON for unexpected backend exceptions
- surfacing distinct frontend messages for network, HTTP, and parse failures
- providing `mentor-groups-dev`, which starts a matched frontend/backend pair together

### Debug Checklist

1. Start the stack with `mentor-groups-dev`.
2. Open the frontend URL printed by the launcher.
3. Verify backend health:
   - `curl http://127.0.0.1:8000/api/health`
   - or use the API URL printed by `mentor-groups-dev`
4. If you run the frontend separately, set `VITE_API_BASE_URL` explicitly.
5. Read the frontend banner:
   - `Could not reach the backend` means network, proxy, or base-URL failure
   - `Backend returned HTTP ...` means the backend responded with an error body
   - `response was not valid JSON` means the route returned malformed JSON
6. Run the automated checks:
   - `.venv/bin/pytest`
   - `cd frontend && npm test`
   - `cd frontend && npm run build`
7. If sample loading fails, verify [data_raw/converted/scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/data_raw/converted/scenario.json) exists and is valid JSON.
8. If solving fails, run `Check inputs` first and inspect fatal issues and warnings.

## Known Limitations

- The one-command launcher still depends on local `node` / `npm` being available so the frontend can be built.
- The optimization is weighted CP-SAT, not a full lexicographic multi-pass proof of every priority layer.
- Requested partners remain soft and may be unsatisfied in tight scenarios.
- International extra mentors are modeled as total extra normal capacity with a preference toward two-period normals, not a hard “all three extras must be two-period” rule.
- The UI is intentionally practical and still lives mostly in one large React screen.

## Future Improvements

- Add frontend build/test coverage in CI
- Split the React screen into smaller typed components
- Add richer infeasibility diagnostics before solve
- Add manual leader-pairing diagnostics and optional co-leader objectives
- Add scenario persistence beyond browser local storage
