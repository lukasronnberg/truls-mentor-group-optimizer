from __future__ import annotations

import logging
import time
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles

from .example_data import build_example_scenario
from .import_export import (
    groups_to_csv,
    parse_blocked_pairs_csv,
    parse_mentors_csv,
    parse_scenario_json,
)
from .models import BlockedPair, Mentor, ScenarioInput, SolveResponse, ValidationResponse, WorkspaceState
from .solver import solve_scenario
from .validation import analyze_scenario
from .workspace_store import load_workspace, save_workspace


logger = logging.getLogger("mentor_groups.api")

app = FastAPI(title="Mentor Group Optimizer", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
        raise
    duration_ms = round((time.perf_counter() - start_time) * 1000, 1)
    logger.info(
        "%s %s -> %s in %sms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    response.headers["X-Process-Time-Ms"] = str(duration_ms)
    return response


@app.exception_handler(Exception)
async def handle_unexpected_exception(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("Unhandled server error for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=500,
        content={
            "detail": "Internal server error.",
            "path": request.url.path,
            "method": request.method,
        },
    )


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/api/example", response_model=ScenarioInput)
def example() -> ScenarioInput:
    return build_example_scenario()


@app.get("/api/workspace", response_model=WorkspaceState)
def get_workspace() -> WorkspaceState:
    return load_workspace()


@app.post("/api/workspace", response_model=WorkspaceState)
def put_workspace(workspace: WorkspaceState) -> WorkspaceState:
    return save_workspace(workspace)


@app.post("/api/validate", response_model=ValidationResponse)
def validate_scenario(scenario: ScenarioInput) -> ValidationResponse:
    return analyze_scenario(scenario)


@app.post("/api/import/scenario-json", response_model=ScenarioInput)
async def import_scenario_json(file: UploadFile = File(...)) -> ScenarioInput:
    try:
        return parse_scenario_json((await file.read()).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/import/mentors-csv", response_model=list[Mentor])
async def import_mentors_csv(file: UploadFile = File(...)) -> list[Mentor]:
    try:
        return parse_mentors_csv((await file.read()).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/import/blocked-pairs-csv", response_model=list[BlockedPair])
async def import_blocked_pairs_csv(file: UploadFile = File(...)) -> list[BlockedPair]:
    try:
        return parse_blocked_pairs_csv((await file.read()).decode("utf-8"))
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/solve", response_model=SolveResponse)
def solve(scenario: ScenarioInput) -> SolveResponse:
    return solve_scenario(scenario)


@app.post("/api/export/groups-csv")
def export_groups_csv(solution: SolveResponse) -> PlainTextResponse:
    if solution.status == "infeasible":
        raise HTTPException(status_code=400, detail="Cannot export groups from an infeasible solve.")
    csv_content = groups_to_csv(solution.assignments)
    return PlainTextResponse(
        csv_content,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="mentor-groups.csv"'},
    )


frontend_dist = Path(__file__).resolve().parents[2] / "frontend" / "dist"
if frontend_dist.exists():
    app.mount("/", StaticFiles(directory=frontend_dist, html=True), name="frontend")
