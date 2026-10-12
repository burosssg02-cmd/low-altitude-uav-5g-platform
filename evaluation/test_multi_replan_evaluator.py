import pytest

from evaluation.multi_replan_evaluator import (
    _build_apply_event_map,
    _communication_change,
    _find_matching_degradation,
    _find_recovery_after,
)


def _degraded(
    *,
    time: str,
    east: float,
    north: float,
    rsrp: float = -98.0,
    sinr: float = 1.0,
    score: float = 0.49,
) -> dict:
    return {
        "event_type": "COMMUNICATION_DEGRADED",
        "timestamp_utc": time,
        "east_m": east,
        "north_m": north,
        "rsrp_dbm": rsrp,
        "sinr_db": sinr,
        "coverage_score": score,
    }


def _recovered(
    *,
    time: str,
    east: float,
    north: float,
    rsrp: float = -80.0,
    sinr: float = 4.0,
    score: float = 0.80,
) -> dict:
    return {
        "event_type": "COMMUNICATION_RECOVERED",
        "timestamp_utc": time,
        "east_m": east,
        "north_m": north,
        "rsrp_dbm": rsrp,
        "sinr_db": sinr,
        "coverage_score": score,
    }


def test_match_two_degradations_in_order():
    events = [
        _degraded(
            time="2026-10-09T02:13:41+00:00",
            east=22.2,
            north=15.0,
        ),
        _recovered(
            time="2026-10-09T02:13:51+00:00",
            east=20.0,
            north=6.2,
        ),
        _degraded(
            time="2026-10-09T02:13:54+00:00",
            east=20.0,
            north=5.1,
        ),
        _recovered(
            time="2026-10-09T02:13:55+00:00",
            east=20.0,
            north=4.0,
        ),
    ]

    decision_1 = {
        "context": {
            "east_m": 22.18,
            "north_m": 15.03,
        }
    }

    decision_2 = {
        "context": {
            "east_m": 20.01,
            "north_m": 5.08,
        }
    }

    index_1, event_1 = (
        _find_matching_degradation(
            decision=decision_1,
            communication_events=events,
            start_index=0,
        )
    )

    index_2, event_2 = (
        _find_matching_degradation(
            decision=decision_2,
            communication_events=events,
            start_index=index_1 + 1,
        )
    )

    assert index_1 == 0
    assert index_2 == 2

    assert (
        event_1["event_type"]
        == "COMMUNICATION_DEGRADED"
    )

    assert (
        event_2["event_type"]
        == "COMMUNICATION_DEGRADED"
    )


def test_matching_rejects_far_incident():
    events = [
        _degraded(
            time="2026-10-09T02:13:41+00:00",
            east=20.0,
            north=15.0,
        )
    ]

    decision = {
        "context": {
            "east_m": 40.0,
            "north_m": 40.0,
        }
    }

    with pytest.raises(
        RuntimeError,
        match="away from decision context",
    ):
        _find_matching_degradation(
            decision=decision,
            communication_events=events,
            start_index=0,
        )


def test_recovery_is_paired_with_same_episode():
    events = [
        _degraded(
            time="2026-10-09T02:13:41+00:00",
            east=22.2,
            north=15.0,
        ),
        _recovered(
            time="2026-10-09T02:13:51+00:00",
            east=20.0,
            north=6.2,
        ),
        _degraded(
            time="2026-10-09T02:13:54+00:00",
            east=20.0,
            north=5.1,
        ),
    ]

    recovery = _find_recovery_after(
        communication_events=events,
        degradation_index=0,
    )

    assert recovery is not None

    assert (
        recovery["event_type"]
        == "COMMUNICATION_RECOVERED"
    )

    assert recovery["east_m"] == 20.0


def test_recovery_does_not_cross_next_degradation():
    events = [
        _degraded(
            time="2026-10-09T02:13:41+00:00",
            east=22.2,
            north=15.0,
        ),
        _degraded(
            time="2026-10-09T02:13:42+00:00",
            east=21.0,
            north=10.0,
        ),
        _recovered(
            time="2026-10-09T02:13:50+00:00",
            east=20.0,
            north=5.0,
        ),
    ]

    recovery = _find_recovery_after(
        communication_events=events,
        degradation_index=0,
    )

    assert recovery is None


def test_apply_map_and_communication_improvement():
    route_events = [
        {
            "event_type":
                "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
            "timestamp_utc":
                "2026-10-09T02:13:41.530+00:00",
            "metadata": {
                "replan_index": 1,
                "waypoint_count": 6,
            },
        },
        {
            "event_type":
                "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
            "timestamp_utc":
                "2026-10-09T02:13:54.428+00:00",
            "metadata": {
                "replan_index": 2,
                "waypoint_count": 4,
            },
        },
    ]

    mapping = _build_apply_event_map(
        route_events
    )

    assert set(mapping) == {1, 2}

    assert (
        mapping[1]["metadata"][
            "waypoint_count"
        ]
        == 6
    )

    assert (
        mapping[2]["metadata"][
            "waypoint_count"
        ]
        == 4
    )

    degradation = _degraded(
        time="2026-10-09T02:13:41+00:00",
        east=22.2,
        north=15.0,
        rsrp=-98.0,
        sinr=1.0,
        score=0.49,
    )

    recovery = _recovered(
        time="2026-10-09T02:13:51+00:00",
        east=20.0,
        north=6.2,
        rsrp=-80.0,
        sinr=4.0,
        score=0.80,
    )

    change = _communication_change(
        degradation,
        recovery,
    )

    assert change is not None

    assert (
        change["rsrp_improvement_db"]
        == pytest.approx(18.0)
    )

    assert (
        change["sinr_improvement_db"]
        == pytest.approx(3.0)
    )

    assert (
        change[
            "coverage_score_improvement"
        ]
        == pytest.approx(0.31)
    )


def test_full_multi_replan_evaluation_end_to_end(
    tmp_path,
):
    import csv
    import json

    from evaluation.multi_replan_evaluator import (
        evaluate_multi_replan,
    )

    run_dir = tmp_path / "synthetic_multi_replan"
    run_dir.mkdir()

    # ====================================================
    # 1. Planned route
    # Original route:
    # (1,3) -> (2,3) -> (3,3) -> (4,3)
    # 5 m grid resolution, total 15 m.
    # ====================================================

    planned_rows = [
        {
            "waypoint_id": "WP0",
            "grid_x": 1,
            "grid_y": 3,
            "east_m": 0.0,
            "north_m": 0.0,
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "relative_altitude_m": 5.0,
        },
        {
            "waypoint_id": "WP1",
            "grid_x": 2,
            "grid_y": 3,
            "east_m": 5.0,
            "north_m": 0.0,
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "relative_altitude_m": 5.0,
        },
        {
            "waypoint_id": "WP2",
            "grid_x": 3,
            "grid_y": 3,
            "east_m": 10.0,
            "north_m": 0.0,
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "relative_altitude_m": 5.0,
        },
        {
            "waypoint_id": "WP3",
            "grid_x": 4,
            "grid_y": 3,
            "east_m": 15.0,
            "north_m": 0.0,
            "latitude_deg": 0.0,
            "longitude_deg": 0.0,
            "relative_altitude_m": 5.0,
        },
    ]

    with (
        run_dir / "planned_waypoints.csv"
    ).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                planned_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            planned_rows
        )

    # ====================================================
    # 2. Actual trajectory
    #
    # It intentionally follows the detour created by
    # the runtime replans.
    # ====================================================

    actual_rows = [
        {
            "sample_index": 0,
            "timestamp_utc":
                "2026-10-09T00:00:00+00:00",
            "elapsed_s": 0.0,
            "east_m": 0.0,
            "north_m": 0.0,
            "in_air": "True",
            "target_waypoint": "WP1",
        },
        {
            "sample_index": 1,
            "timestamp_utc":
                "2026-10-09T00:00:10+00:00",
            "elapsed_s": 10.0,
            "east_m": 5.0,
            "north_m": 0.0,
            "in_air": "True",
            "target_waypoint": "R1_WP1",
        },
        {
            "sample_index": 2,
            "timestamp_utc":
                "2026-10-09T00:00:15+00:00",
            "elapsed_s": 15.0,
            "east_m": 5.0,
            "north_m": 5.0,
            "in_air": "True",
            "target_waypoint": "R1_WP2",
        },
        {
            "sample_index": 3,
            "timestamp_utc":
                "2026-10-09T00:00:18+00:00",
            "elapsed_s": 18.0,
            "east_m": 8.0,
            "north_m": 5.0,
            "in_air": "True",
            "target_waypoint": "R1_WP2",
        },
        {
            "sample_index": 4,
            "timestamp_utc":
                "2026-10-09T00:00:20+00:00",
            "elapsed_s": 20.0,
            "east_m": 10.0,
            "north_m": 5.0,
            "in_air": "True",
            "target_waypoint": "R2_WP1",
        },
        {
            "sample_index": 5,
            "timestamp_utc":
                "2026-10-09T00:00:25+00:00",
            "elapsed_s": 25.0,
            "east_m": 15.0,
            "north_m": 5.0,
            "in_air": "True",
            "target_waypoint": "R2_WP2",
        },
        {
            "sample_index": 6,
            "timestamp_utc":
                "2026-10-09T00:00:30+00:00",
            "elapsed_s": 30.0,
            "east_m": 15.0,
            "north_m": 0.0,
            "in_air": "False",
            "target_waypoint": "LANDED",
        },
    ]

    with (
        run_dir / "actual_trajectory.csv"
    ).open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=list(
                actual_rows[0].keys()
            ),
        )

        writer.writeheader()
        writer.writerows(
            actual_rows
        )

    # ====================================================
    # 3. Mission summary
    # ====================================================

    (
        run_dir
        / "mission_summary.json"
    ).write_text(
        json.dumps(
            {
                "planned_distance_m": 15.0,
                "actual_distance_m": 30.0,
                "flight_efficiency": 0.5,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # ====================================================
    # 4. Communication + incident events
    # ====================================================

    incident_document = {
        "schema_version": "1.0",
        "incident_records": [],
        "communication_events": [
            {
                "event_type":
                    "COMMUNICATION_DEGRADED",
                "timestamp_utc":
                    "2026-10-09T00:00:10+00:00",
                "elapsed_s": 10.0,
                "east_m": 5.0,
                "north_m": 0.0,
                "rsrp_dbm": -98.0,
                "sinr_db": 1.0,
                "coverage_score": 0.49,
            },
            {
                "event_type":
                    "COMMUNICATION_RECOVERED",
                "timestamp_utc":
                    "2026-10-09T00:00:18+00:00",
                "elapsed_s": 18.0,
                "east_m": 8.0,
                "north_m": 5.0,
                "rsrp_dbm": -82.0,
                "sinr_db": 4.0,
                "coverage_score": 0.78,
            },
            {
                "event_type":
                    "COMMUNICATION_DEGRADED",
                "timestamp_utc":
                    "2026-10-09T00:00:20+00:00",
                "elapsed_s": 20.0,
                "east_m": 10.0,
                "north_m": 5.0,
                "rsrp_dbm": -96.0,
                "sinr_db": 2.0,
                "coverage_score": 0.55,
            },
            {
                "event_type":
                    "COMMUNICATION_RECOVERED",
                "timestamp_utc":
                    "2026-10-09T00:00:30+00:00",
                "elapsed_s": 30.0,
                "east_m": 15.0,
                "north_m": 0.0,
                "rsrp_dbm": -80.0,
                "sinr_db": 5.0,
                "coverage_score": 0.81,
            },
        ],
    }

    (
        run_dir
        / "incident_events.json"
    ).write_text(
        json.dumps(
            incident_document,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ====================================================
    # 5. Two runtime replans
    # ====================================================

    def decision(
        *,
        east,
        north,
        grid,
        path,
        latency,
    ):
        return {
            "event_type":
                "COMMUNICATION_DEGRADED",
            "action":
                "REPLAN_QUEUED",

            "context": {
                "east_m": east,
                "north_m": north,
            },

            "decision": {
                "decision":
                    "REPLAN_RECOMMENDED",
                "selected_planner":
                    "communication_aware",
                "reason":
                    "Synthetic test replan",
                "triggered_rules": [
                    "MEAN_SCORE_IMPROVED",
                    "MEAN_RSRP_IMPROVED",
                ],
                "metrics": {},
            },

            "decision_source":
                "FAST_POLICY",

            "compare_latency_s":
                latency * 0.8,

            "policy_latency_s":
                latency * 0.2,

            "fast_decision_latency_s":
                latency,

            "latest_position": {
                "east_m": east,
                "north_m": north,
            },

            "decision_position_drift_m":
                0.0,

            "incident_grid":
                list(grid),

            "replan_current_grid":
                list(grid),

            "replan_path": [
                list(node)
                for node in path
            ],

            "accepted":
                True,
        }

    replan_document = {
        "schema_version": "1.0",

        "replan_decisions": [
            decision(
                east=5.0,
                north=0.0,
                grid=(2, 3),
                path=[
                    (2, 3),
                    (2, 2),
                    (3, 2),
                    (4, 2),
                    (4, 3),
                ],
                latency=0.001,
            ),
            decision(
                east=10.0,
                north=5.0,
                grid=(3, 2),
                path=[
                    (3, 2),
                    (4, 2),
                    (4, 3),
                ],
                latency=0.0005,
            ),
        ],

        "route_application_events": [
            {
                "event_type":
                    "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
                "timestamp_utc":
                    "2026-10-09T00:00:10.003+00:00",
                "metadata": {
                    "replan_index": 1,
                    "waypoint_count": 4,
                },
            },
            {
                "event_type":
                    "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
                "timestamp_utc":
                    "2026-10-09T00:00:20.002+00:00",
                "metadata": {
                    "replan_index": 2,
                    "waypoint_count": 2,
                },
            },
        ],
    }

    (
        run_dir
        / "runtime_replans.json"
    ).write_text(
        json.dumps(
            replan_document,
            indent=2,
        ),
        encoding="utf-8",
    )

    # ====================================================
    # 6. Run complete evaluator
    # ====================================================

    result = evaluate_multi_replan(
        run_dir
    )

    assert (
        result["evaluation_mode"]
        == "MULTI_REPLAN"
    )

    assert (
        result["episode_count"]
        == 2
    )

    assert (
        result["overall"][
            "replan_count"
        ]
        == 2
    )

    assert (
        result["overall"][
            "recovery_count"
        ]
        == 2
    )

    assert (
        result["episodes"][0][
            "route_application"
        ][
            "replan_index"
        ]
        == 1
    )

    assert (
        result["episodes"][1][
            "route_application"
        ][
            "replan_index"
        ]
        == 2
    )

    assert (
        result["episodes"][0][
            "fast_policy"
        ][
            "total_latency_s"
        ]
        == pytest.approx(
            0.001
        )
    )

    assert (
        result["episodes"][1][
            "fast_policy"
        ][
            "total_latency_s"
        ]
        == pytest.approx(
            0.0005
        )
    )

    assert (
        result["overall"][
            "mean_fast_decision_latency_s"
        ]
        == pytest.approx(
            0.00075
        )
    )

    assert (
        result["overall"][
            "revised_total_planned_distance_m"
        ]
        == pytest.approx(
            25.0
        )
    )

    assert (
        result["overall"][
            "dynamic_extra_distance_m"
        ]
        == pytest.approx(
            5.0
        )
    )

    assert (
        result["overall"][
            "dynamic_flight_efficiency"
        ]
        == pytest.approx(
            25.0 / 30.0
        )
    )

    output_path = (
        run_dir
        / "multi_replan_evaluation.json"
    )

    assert output_path.exists()

    saved = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        saved["episode_count"]
        == 2
    )


def test_multi_replan_if_available_skips_single_replan(
    tmp_path,
):
    import json

    from evaluation.multi_replan_evaluator import (
        evaluate_multi_replan_if_available,
    )

    runtime_document = {
        "replan_decisions": [
            {
                "action":
                    "REPLAN_QUEUED",
            }
        ],
        "route_application_events": [
            {
                "event_type":
                    "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
            }
        ],
    }

    (
        tmp_path
        / "runtime_replans.json"
    ).write_text(
        json.dumps(
            runtime_document
        ),
        encoding="utf-8",
    )

    result = (
        evaluate_multi_replan_if_available(
            tmp_path
        )
    )

    assert result is None


def test_multi_replan_if_available_runs_for_two_replans(
    tmp_path,
    monkeypatch,
):
    import json

    import evaluation.multi_replan_evaluator as module

    runtime_document = {
        "replan_decisions": [
            {
                "action":
                    "REPLAN_QUEUED",
            },
            {
                "action":
                    "REPLAN_QUEUED",
            },
        ],
        "route_application_events": [
            {
                "event_type":
                    "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
            },
            {
                "event_type":
                    "RUNTIME_ROUTE_REPLACEMENT_APPLIED",
            },
        ],
    }

    (
        tmp_path
        / "runtime_replans.json"
    ).write_text(
        json.dumps(
            runtime_document
        ),
        encoding="utf-8",
    )

    expected = {
        "evaluation_mode":
            "MULTI_REPLAN",
        "episode_count":
            2,
    }

    called = {
        "count": 0,
    }

    def fake_evaluate(
        run_dir,
    ):
        called["count"] += 1

        assert run_dir == tmp_path

        return expected

    monkeypatch.setattr(
        module,
        "evaluate_multi_replan",
        fake_evaluate,
    )

    result = (
        module
        .evaluate_multi_replan_if_available(
            tmp_path
        )
    )

    assert result == expected
    assert called["count"] == 1
