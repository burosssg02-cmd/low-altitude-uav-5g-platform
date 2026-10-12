import csv
import json

from pathlib import Path

from evaluation.dynamic_replan_evaluator import (
    evaluate_dynamic_replan,
)


def _write_csv(
    path: Path,
    rows: list[dict],
):
    with path.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def test_structured_dynamic_evaluation_without_log(
    tmp_path,
):
    run_dir = tmp_path

    planned = [
        {
            "waypoint_id": "WP0",
            "grid_x": 1,
            "grid_y": 3,
            "east_m": 0.0,
            "north_m": 0.0,
        },
        {
            "waypoint_id": "WP1",
            "grid_x": 3,
            "grid_y": 3,
            "east_m": 10.0,
            "north_m": 0.0,
        },
        {
            "waypoint_id": "WP2",
            "grid_x": 3,
            "grid_y": 0,
            "east_m": 10.0,
            "north_m": 15.0,
        },
        {
            "waypoint_id": "WP3",
            "grid_x": 8,
            "grid_y": 0,
            "east_m": 35.0,
            "north_m": 15.0,
        },
        {
            "waypoint_id": "WP4",
            "grid_x": 8,
            "grid_y": 3,
            "east_m": 35.0,
            "north_m": 0.0,
        },
    ]

    actual = [
        {
            "timestamp_utc":
                "2026-10-08T10:53:00+00:00",
            "east_m": 0.0,
            "north_m": 0.0,
            "in_air": "True",
            "target_waypoint": "TAKEOFF",
        },
        {
            "timestamp_utc":
                "2026-10-08T10:53:20+00:00",
            "east_m": 10.0,
            "north_m": 15.0,
            "in_air": "True",
            "target_waypoint": "WP3",
        },
        {
            "timestamp_utc":
                "2026-10-08T10:53:27+00:00",
            "east_m": 22.4,
            "north_m": 14.9,
            "in_air": "True",
            "target_waypoint": "WP3",
        },
        {
            "timestamp_utc":
                "2026-10-08T10:53:27.200000+00:00",
            "east_m": 22.5,
            "north_m": 14.9,
            "in_air": "True",
            "target_waypoint": "R1_WP1",
        },
        {
            "timestamp_utc":
                "2026-10-08T10:53:32+00:00",
            "east_m": 20.0,
            "north_m": 10.0,
            "in_air": "True",
            "target_waypoint": "R1_WP1",
        },
        {
            "timestamp_utc":
                "2026-10-08T10:53:38.500000+00:00",
            "east_m": 20.0,
            "north_m": 5.8,
            "in_air": "True",
            "target_waypoint": "R1_WP2",
        },
        {
            "timestamp_utc":
                "2026-10-08T10:54:07+00:00",
            "east_m": 35.0,
            "north_m": 0.0,
            "in_air": "False",
            "target_waypoint": "LANDED",
        },
    ]

    _write_csv(
        run_dir
        / "planned_waypoints.csv",
        planned,
    )

    _write_csv(
        run_dir
        / "actual_trajectory.csv",
        actual,
    )

    (
        run_dir
        / "mission_summary.json"
    ).write_text(
        json.dumps(
            {
                "planned_distance_m":
                    65.0,

                "actual_distance_m":
                    79.59,

                "flight_efficiency":
                    65.0 / 79.59,
            }
        ),
        encoding="utf-8",
    )

    (
        run_dir
        / "communication_summary.json"
    ).write_text(
        json.dumps(
            {
                "samples": 100,
                "mean_rsrp_dbm": -81.0,
                "mean_sinr_db": 5.0,
            }
        ),
        encoding="utf-8",
    )

    (
        run_dir
        / "incident_events.json"
    ).write_text(
        json.dumps(
            {
                "mission": {
                    "planner": "normal",
                    "start": [1, 3],
                    "goal": [8, 3],
                    "altitude_m": 5.0,
                    "communication_weight": 2.0,
                },

                "incident_records": [
                    {
                        "event_type":
                            "INCIDENT_ADVISORY",

                        "action":
                            "ADVISOR_FAILED",

                        "background_latency_s":
                            5.289,

                        "result": {
                            "status":
                                "FAILED",
                        },
                    }
                ],

                "communication_events": [
                    {
                        "event_type":
                            "COMMUNICATION_DEGRADED",

                        "timestamp_utc":
                            "2026-10-08T10:53:27+00:00",

                        "elapsed_s":
                            27.0,

                        "east_m":
                            22.4,

                        "north_m":
                            14.9,

                        "rsrp_dbm":
                            -97.9,

                        "sinr_db":
                            1.9,

                        "coverage_score":
                            0.491,
                    },
                    {
                        "event_type":
                            "COMMUNICATION_RECOVERED",

                        "timestamp_utc":
                            "2026-10-08T10:53:38.500000+00:00",

                        "elapsed_s":
                            38.5,

                        "east_m":
                            20.0,

                        "north_m":
                            5.8,

                        "rsrp_dbm":
                            -78.1,

                        "sinr_db":
                            4.74,

                        "coverage_score":
                            0.796,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )

    (
        run_dir
        / "runtime_replans.json"
    ).write_text(
        json.dumps(
            {
                "replan_decisions": [
                    {
                        "event_type":
                            "COMMUNICATION_DEGRADED",

                        "action":
                            "REPLAN_QUEUED",

                        "decision_source":
                            "FAST_POLICY",

                        "fast_decision_latency_s":
                            0.0015,

                        "decision": {
                            "decision":
                                "REPLAN_RECOMMENDED",

                            "selected_planner":
                                "communication_aware",

                            "reason":
                                "Communication "
                                "improvement is sufficient.",
                        },

                        "latest_position": {
                            "east_m":
                                22.4,

                            "north_m":
                                14.9,
                        },

                        "incident_grid":
                            [5, 0],

                        "replan_current_grid":
                            [5, 0],

                        "decision_position_drift_m":
                            0.0,

                        "replan_path": [
                            [5, 0],
                            [5, 1],
                            [5, 2],
                            [5, 3],
                            [6, 3],
                            [7, 3],
                            [8, 3],
                        ],
                    }
                ],

                "route_application_events": [
                    {
                        "event_type":
                            "RUNTIME_ROUTE_REPLACEMENT_APPLIED",

                        "timestamp_utc":
                            "2026-10-08T10:53:27.200000+00:00",

                        "metadata": {
                            "waypoint_count":
                                6,

                            "replan_index":
                                1,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    summary = (
        evaluate_dynamic_replan(
            run_dir
        )
    )

    assert (
        summary[
            "artifact_source"
        ]
        ==
        "STRUCTURED_RUNTIME_ARTIFACTS"
    )

    assert (
        summary[
            "log_file_required"
        ]
        is False
    )

    assert (
        summary[
            "mission_status"
        ]
        == "COMPLETED"
    )

    assert (
        summary[
            "fast_policy"
        ][
            "decision_source"
        ]
        == "FAST_POLICY"
    )

    assert (
        summary[
            "route_application"
        ][
            "incident_to_route_apply_s"
        ]
        == 0.2
    )

    assert (
        summary[
            "recovery"
        ][
            "incident_to_recovery_s"
        ]
        == 11.5
    )

    assert (
        summary[
            "communication_change"
        ][
            "rsrp_improvement_db"
        ]
        > 19.0
    )

    assert (
        run_dir
        / "dynamic_replan_evaluation.json"
    ).exists()

    assert (
        run_dir
        / "dynamic_route_waypoints.csv"
    ).exists()

    assert (
        run_dir
        / "dynamic_trajectory_comparison.png"
    ).exists()


def test_dynamic_evaluation_skips_normal_mission(
    tmp_path,
):
    from evaluation.dynamic_replan_evaluator import (
        evaluate_dynamic_replan_if_available,
    )

    (
        tmp_path
        / "runtime_replans.json"
    ).write_text(
        json.dumps(
            {
                "replan_decisions": [],
                "route_application_events": [],
            }
        ),
        encoding="utf-8",
    )

    result = (
        evaluate_dynamic_replan_if_available(
            tmp_path
        )
    )

    assert result is None
