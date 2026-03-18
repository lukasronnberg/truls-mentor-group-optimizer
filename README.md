# TRULS

TRULS is a local-first mentor group optimization tool built with FastAPI, OR-Tools CP-SAT, React, and TypeScript.

It is designed to help organizers generate mentor-group proposals for two periods under real operational constraints such as blocked pairs, international-group rules, requested partners, leader placement, event spread, and balanced additive pools.

## AI-Generated Code Notice

This repository is intentionally presented as an AI-generated portfolio project.

- All application code in this repository was generated and iteratively refined with AI assistance.
- The project is being published as a demonstration of product framing, iterative specification, constraint modeling, evaluation, and AI-assisted engineering workflow.
- It should not be represented as hand-written-from-scratch production software.

## Portfolio Framing

This project demonstrates:

- constraint optimization with OR-Tools CP-SAT
- structured domain modeling with Pydantic
- a local-first web workflow with FastAPI + React
- iterative product refinement from vague rules to enforceable solver logic
- AI-assisted end-to-end engineering across backend, frontend, validation, reporting, and DX

## Tech Stack

- Python
- FastAPI
- OR-Tools CP-SAT
- Pydantic
- React
- TypeScript
- Vite
- pytest

## Core Features

- two-period mentor-group generation with hard and soft constraints
- explicit leader modeling with one `head` and one `vice` per group
- additive `sexi` and `hovding` pools on top of the normal base quota
- blocked-pair enforcement
- requested-partner optimization
- international-group rules
- event-mentor spread controls
- compact analytical UI branded as `TRULS`
- local workspace persistence for scenario data and saved proposals
- CSV / JSON import and CSV export
- human-readable compromise reporting

## Public Repository Scope

This public repository contains:

- source code
- synthetic demo/example datasets
- tests
- documentation

This public repository intentionally does **not** include:

- private working workspace state in `.truls/`
- raw local input files in `data_raw/`
- machine-specific virtual environments or build artifacts

## Architecture

- [backend/app/models.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/models.py): domain models, API schemas, validation contracts
- [backend/app/validation.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/validation.py): fatal errors and pre-solve warnings
- [backend/app/solver.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/solver.py): CP-SAT model and solve pipeline
- [backend/app/scoring.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/scoring.py): weighted soft-goal definitions and score breakdown
- [backend/app/reporting.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/reporting.py): compromise reporting and rule summaries
- [backend/app/import_export.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/import_export.py): CSV/JSON import and CSV export
- [backend/app/workspace_store.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/workspace_store.py): local workspace persistence
- [backend/app/main.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/main.py): FastAPI routes
- [backend/app/launcher.py](/Users/lukasronnberg/Documents/Phøs/truls/backend/app/launcher.py): one-command launcher
- [frontend/src/App.tsx](/Users/lukasronnberg/Documents/Phøs/truls/frontend/src/App.tsx): TRULS UI
- [frontend/src/api.ts](/Users/lukasronnberg/Documents/Phøs/truls/frontend/src/api.ts): frontend API client and error handling
- [examples/](/Users/lukasronnberg/Documents/Phøs/truls/examples): synthetic demo scenarios and CSV imports
- [tests/](/Users/lukasronnberg/Documents/Phøs/truls/tests): backend regression tests

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
- `normal_subrole=international` means the mentor must be placed in the international group in every participated period
- `sexi` mentors are additive and do not count toward the normal base quota
- `hovding` mentors are additive leaders and do not count toward the normal base quota

## Group Composition

Regular group, per period:

- 2 one-period normal mentors
- 5 two-period normal mentors
- additive `sexi` mentors
- 2 leaders on top:
  - 1 `head`
  - 1 `vice`

International group, per period:

- same normal base: `2 + 5`
- plus 3 extra normal mentors
- additive `sexi` mentors
- 2 leaders on top:
  - 1 `head`
  - 1 `vice`

## Solver Strategy

The solver uses one assignment variable per mentor / period / group, plus explicit leader-role variables.

Hard constraints include:

- blocked pairs never share a group
- one-period mentors are assigned exactly once
- two-period mentors are assigned once per period
- each group gets exactly one `head` and one `vice`
- each leader is `head` once and `vice` once
- `international`-marked mentors are hard-assigned to the international group in every participated period
- non-international mentors may be assigned to an international group in at most one period
- event mentors have an absolute max of 2 per group

Soft goals include:

- at least one requested partner in each participated period
- preferred period for one-period normal mentors
- minimizing repeated groupmates across periods
- strong balancing of `sexi` spread
- event spread
- gender and year balance
- preferring two-period normals for international extra slots

## Configurable Weights

Weights live in `ScenarioInput.weights`.

- `quota_shortfall`
- `quota_overflow`
- `international_extra_two_period_shortfall`
- `international_preference`
- `nonpreferred_international`
- `request_missing`
- `preferred_period_miss`
- `repeated_groupmates`
- `event_second_mentor`
- `event_evenness`
- `sexi_evenness`
- `balance_gender`
- `balance_year`

## Workspace Persistence

TRULS now persists local working state through the backend in:

- `.truls/workspace.json`

That workspace stores:

- the current scenario
- saved proposals

This allows the app to preserve state across restarts even if the local dev server comes back on a different port.

## API

Main endpoints:

- `GET /api/health`
- `GET /api/example`
- `GET /api/workspace`
- `POST /api/workspace`
- `POST /api/validate`
- `POST /api/solve`
- `POST /api/import/scenario-json`
- `POST /api/import/mentors-csv`
- `POST /api/import/blocked-pairs-csv`
- `POST /api/export/groups-csv`

## Demo Data

Synthetic demo files:

- [examples/demo_scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_scenario.json)
- [examples/demo_mentors.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_mentors.csv)
- [examples/demo_blocked_pairs.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/demo_blocked_pairs.csv)
- [examples/tight_scenario.json](/Users/lukasronnberg/Documents/Phøs/truls/examples/tight_scenario.json)
- [examples/tight_mentors.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/tight_mentors.csv)
- [examples/tight_blocked_pairs.csv](/Users/lukasronnberg/Documents/Phøs/truls/examples/tight_blocked_pairs.csv)

## Local Run

Create the Python environment and install backend dependencies:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Run the full app in one command:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
source .venv/bin/activate
mentor-groups-dev
```

## Shareable Bundle

Build a shareable folder for friends:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
source .venv/bin/activate
mentor-groups-bundle
```

This creates:

- `release/TRULS/`

That folder includes:

- the backend source
- a prebuilt frontend
- synthetic demo data
- a one-click launcher: `Start TRULS.command`

For friends:

- they only need Python 3.11+
- they do not need Node.js
- on first launch, the bundle creates its own local `.venv`
- saved state stays inside the shared folder under `.truls/`

Or run the backend only:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
source .venv/bin/activate
uvicorn backend.app.main:app --reload
```

Frontend only:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls/frontend
npm install
npm run dev
```

## Tests

Backend:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls
source .venv/bin/activate
pytest -q
```

Frontend:

```bash
cd /Users/lukasronnberg/Documents/Phøs/truls/frontend
npm test -- --run
npm run build
```

## Known Limitations

- this is an AI-generated portfolio project, not a hardened production system
- optimization is still weighted CP-SAT, not a fully lexicographic proof of each priority layer
- requested partners remain soft and can still be missed in tight scenarios
- the frontend is practical and compact, but still centered around a large application shell
- local launch still depends on `node` / `npm` being installed

## License

MIT
