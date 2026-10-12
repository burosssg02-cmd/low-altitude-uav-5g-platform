import json

from fastapi.testclient import (
    TestClient,
)

from backend.main import app

from backend.services import (
    run_artifact_service,
)


client = TestClient(
    app
)


def write_json(
    path,
    data,
):
    path.write_text(
        json.dumps(
            data
        ),
        encoding="utf-8",
    )


def create_complete_run(
    runs_root,
):
    run_dir = (
        runs_root
        / (
            "20261009_120000_"
            "mission_dashboard_test"
        )
    )

    run_dir.mkdir(
        parents=True
    )

    write_json(
        run_dir
        / "mission_summary.json",
        {
            "planned_distance_m":
                65.0,

            "actual_distance_m":
                70.0,

            "mission_duration_s":
                50.0,

            "flight_efficiency":
                65.0 / 70.0,
        },
    )

    write_json(
        run_dir
        / "communication_summary.json",
        {
            "mean_rsrp_dbm":
                -82.0,

            "min_rsrp_dbm":
                -98.0,

            "mean_sinr_db":
                4.5,

            "min_sinr_db":
                0.1,

            "mean_coverage_score":
                0.74,

            "min_coverage_score":
                0.45,
        },
    )

    write_json(
        run_dir
        / "incident_events.json",
        {
            "mission_id":
                "mission_dashboard_test",

            "incident_records": [
                {
                    "event_type":
                        "COMMUNICATION_DEGRADED",
                },
                {
                    "event_type":
                        "INCIDENT_ADVISORY",
                },
            ],
        },
    )

    write_json(
        run_dir
        / "runtime_replans.json",
        {
            "replan_decisions": [
                {
                    "decision":
                        "REPLAN_RECOMMENDED"
                }
            ],

            "route_application_events": [
                {
                    "event_type":
                        (
                            "RUNTIME_ROUTE_"
                            "REPLACEMENT_APPLIED"
                        )
                }
            ],
        },
    )

    (
        run_dir
        / "actual_trajectory.csv"
    ).write_text(
        "elapsed_s,east_m,north_m\n"
        "0.0,0.0,0.0\n",
        encoding="utf-8",
    )

    return run_dir


def test_list_runs_empty(
    tmp_path,
    monkeypatch,
):
    runs_root = (
        tmp_path
        / "runs"
    )

    runs_root.mkdir()

    monkeypatch.setattr(
        run_artifact_service,
        "RUNS_ROOT",
        runs_root,
    )

    response = client.get(
        "/runs"
    )

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()
        == {
            "count": 0,
            "runs": [],
        }
    )


def test_list_runs_summary(
    tmp_path,
    monkeypatch,
):
    runs_root = (
        tmp_path
        / "runs"
    )

    runs_root.mkdir()

    create_complete_run(
        runs_root
    )

    monkeypatch.setattr(
        run_artifact_service,
        "RUNS_ROOT",
        runs_root,
    )

    response = client.get(
        "/runs"
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert data["count"] == 1

    run = data["runs"][0]

    assert (
        run["mission_id"]
        == "mission_dashboard_test"
    )

    assert (
        run["artifact_status"]
        == "COMPLETE"
    )

    assert (
        run["planned_distance_m"]
        == 65.0
    )

    assert (
        run["mean_rsrp_dbm"]
        == -82.0
    )

    assert (
        run["advisor_count"]
        == 1
    )

    assert (
        run["replan_count"]
        == 1
    )


def test_get_run_detail(
    tmp_path,
    monkeypatch,
):
    runs_root = (
        tmp_path
        / "runs"
    )

    runs_root.mkdir()

    run_dir = (
        create_complete_run(
            runs_root
        )
    )

    monkeypatch.setattr(
        run_artifact_service,
        "RUNS_ROOT",
        runs_root,
    )

    response = client.get(
        f"/runs/{run_dir.name}"
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["run"]["mission_id"]
        == "mission_dashboard_test"
    )

    assert (
        data[
            "summaries"
        ][
            "mission_summary"
        ][
            "actual_distance_m"
        ]
        == 70.0
    )

    artifact_names = {
        item["name"]
        for item in data[
            "artifacts"
        ]
    }

    assert (
        "actual_trajectory.csv"
        in artifact_names
    )


def test_partial_run_supported(
    tmp_path,
    monkeypatch,
):
    runs_root = (
        tmp_path
        / "runs"
    )

    runs_root.mkdir()

    run_dir = (
        runs_root
        / (
            "mission_rag_advisor_"
            "dryrun"
        )
    )

    run_dir.mkdir()

    write_json(
        run_dir
        / "rag_advisor_evaluation.json",
        {
            "mission_id":
                (
                    "mission_rag_"
                    "advisor_dryrun"
                ),

            "advisor_success_rate":
                1.0,
        },
    )

    monkeypatch.setattr(
        run_artifact_service,
        "RUNS_ROOT",
        runs_root,
    )

    response = client.get(
        f"/runs/{run_dir.name}"
    )

    assert (
        response.status_code
        == 200
    )

    data = response.json()

    assert (
        data["run"][
            "artifact_status"
        ]
        == "PARTIAL"
    )

    assert (
        data["summaries"][
            "rag_advisor_evaluation"
        ][
            "advisor_success_rate"
        ]
        == 1.0
    )


def test_missing_run_returns_404(
    tmp_path,
    monkeypatch,
):
    runs_root = (
        tmp_path
        / "runs"
    )

    runs_root.mkdir()

    monkeypatch.setattr(
        run_artifact_service,
        "RUNS_ROOT",
        runs_root,
    )

    response = client.get(
        "/runs/does_not_exist"
    )

    assert (
        response.status_code
        == 404
    )


def test_path_traversal_is_rejected(
    tmp_path,
    monkeypatch,
):
    runs_root = (
        tmp_path
        / "runs"
    )

    runs_root.mkdir()

    monkeypatch.setattr(
        run_artifact_service,
        "RUNS_ROOT",
        runs_root,
    )

    # URL-encoded ".." should never resolve
    # outside outputs/runs.
    response = client.get(
        "/runs/%2E%2E"
    )

    assert (
        response.status_code
        in {
            404,
            422,
        }
    )
