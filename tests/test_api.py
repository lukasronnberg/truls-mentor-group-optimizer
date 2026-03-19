import backend.app.main as main
from fastapi.testclient import TestClient
from pathlib import Path

from backend.app.main import app
from backend.app import workspace_store
from tests.test_solver import build_small_scenario


client = TestClient(app)


def test_api_health_validate_and_solve():
    health_response = client.get("/api/health")
    assert health_response.status_code == 200
    assert health_response.json() == {"status": "ok"}

    scenario_payload = build_small_scenario().model_dump(mode="json")

    validate_response = client.post("/api/validate", json=scenario_payload)
    assert validate_response.status_code == 200
    assert validate_response.json()["ok"] is True
    assert "warnings" in validate_response.json()

    solve_response = client.post("/api/solve", json=scenario_payload)
    assert solve_response.status_code == 200
    solved = solve_response.json()
    assert solved["status"] in {"optimal", "feasible"}
    assert len(solved["assignments"]) == 4
    assert "summary" in solved
    assert "score" in solved
    assert "report" in solved


def test_api_workspace_round_trip(tmp_path, monkeypatch):
    monkeypatch.setenv("TRULS_WORKSPACE_DIR", str(tmp_path))
    initial = client.get("/api/workspace")
    assert initial.status_code == 200
    payload = initial.json()
    assert "scenario" in payload
    assert "saved_proposals" in payload

    updated = {
        "scenario": build_small_scenario().model_dump(mode="json"),
        "saved_proposals": [],
    }
    save_response = client.post("/api/workspace", json=updated)
    assert save_response.status_code == 200
    assert save_response.json()["scenario"]["settings"]["groups_per_period"] == 2
    assert Path(workspace_store.get_workspace_file()).exists()


def test_api_example_endpoint_returns_scenario():
    response = client.get("/api/example")
    assert response.status_code == 200
    payload = response.json()
    assert "mentors" in payload
    assert "settings" in payload
    assert payload["settings"]["regular_group_quota_two_period"] == 5


def test_api_export_groups_csv():
    solution = client.post("/api/solve", json=build_small_scenario().model_dump(mode="json")).json()
    export_response = client.post("/api/export/groups-csv", json=solution)
    assert export_response.status_code == 200
    assert "mentor_id" in export_response.text
    assert export_response.headers["content-type"].startswith("text/csv")


def test_api_import_mentors_csv_rejects_missing_columns():
    response = client.post(
        "/api/import/mentors-csv",
        files={"file": ("mentors.csv", "name,category\nAlice,normal\n", "text/csv")},
    )
    assert response.status_code == 400
    assert "missing required columns" in response.text.lower()


def test_api_validate_rejects_malformed_payload():
    response = client.post("/api/validate", json={"mentors": "not-a-list"})
    assert response.status_code == 422


def test_api_example_returns_json_on_internal_error(monkeypatch):
    error_client = TestClient(app, raise_server_exceptions=False)

    def raise_error():
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "build_example_scenario", raise_error)
    response = error_client.get("/api/example")
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error."
    assert response.json()["path"] == "/api/example"


def test_api_solve_returns_json_on_internal_error(monkeypatch):
    error_client = TestClient(app, raise_server_exceptions=False)

    def raise_error(_scenario):
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "solve_scenario", raise_error)
    response = error_client.post("/api/solve", json=build_small_scenario().model_dump(mode="json"))
    assert response.status_code == 500
    assert response.json()["detail"] == "Internal server error."
    assert response.json()["path"] == "/api/solve"


def test_api_health_includes_timing_header():
    response = client.get("/api/health")
    assert response.status_code == 200
    assert "X-Process-Time-Ms" in response.headers
