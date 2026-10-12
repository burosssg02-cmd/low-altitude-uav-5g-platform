from __future__ import annotations

import csv
import json
import math

from datetime import datetime
from pathlib import Path

import matplotlib.pyplot as plt


def _load_csv(
    path: Path,
) -> list[dict]:
    with path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as file:
        return list(
            csv.DictReader(file)
        )


def _load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _parse_time(
    value: str,
) -> datetime:
    return datetime.fromisoformat(
        value
    )


def _distance(
    a: tuple[float, float],
    b: tuple[float, float],
) -> float:
    return math.hypot(
        b[0] - a[0],
        b[1] - a[1],
    )


def _row_point(
    row: dict,
) -> tuple[float, float]:
    return (
        float(
            row["east_m"]
        ),
        float(
            row["north_m"]
        ),
    )


def _trajectory_distance(
    rows: list[dict],
    start_index: int,
    end_index: int,
) -> float:
    if end_index <= start_index:
        return 0.0

    total = 0.0

    for index in range(
        start_index + 1,
        end_index + 1,
    ):
        total += _distance(
            _row_point(
                rows[index - 1]
            ),
            _row_point(
                rows[index]
            ),
        )

    return total


def _nearest_timestamp_index(
    rows: list[dict],
    timestamp_utc: str,
) -> int:
    target = _parse_time(
        timestamp_utc
    )

    return min(
        range(
            len(rows)
        ),
        key=lambda index: abs(
            (
                _parse_time(
                    rows[index][
                        "timestamp_utc"
                    ]
                )
                - target
            ).total_seconds()
        ),
    )


def _project_distance_along_route(
    point: tuple[float, float],
    route: list[
        tuple[float, float]
    ],
) -> float:
    """
    Return distance along the original
    planned polyline to the closest
    projected point.
    """

    best_distance = None
    best_along = 0.0
    cumulative = 0.0

    for index in range(
        len(route) - 1
    ):
        start = route[index]
        end = route[
            index + 1
        ]

        dx = (
            end[0]
            - start[0]
        )

        dy = (
            end[1]
            - start[1]
        )

        length_sq = (
            dx * dx
            + dy * dy
        )

        if length_sq == 0:
            continue

        t = (
            (
                point[0]
                - start[0]
            )
            * dx
            +
            (
                point[1]
                - start[1]
            )
            * dy
        ) / length_sq

        t = max(
            0.0,
            min(
                1.0,
                t,
            ),
        )

        projected = (
            start[0]
            + t * dx,

            start[1]
            + t * dy,
        )

        perpendicular = (
            _distance(
                point,
                projected,
            )
        )

        segment_length = (
            math.sqrt(
                length_sq
            )
        )

        along = (
            cumulative
            + t
            * segment_length
        )

        if (
            best_distance
            is None
            or perpendicular
            < best_distance
        ):
            best_distance = (
                perpendicular
            )

            best_along = (
                along
            )

        cumulative += (
            segment_length
        )

    return best_along


def _infer_grid_resolution(
    planned: list[dict],
) -> float:
    """
    Infer grid resolution from saved
    planned waypoint coordinates.

    This keeps evaluation independent
    from backend planner constants.
    """

    candidates = []

    for index in range(
        len(planned) - 1
    ):
        first = planned[index]
        second = planned[
            index + 1
        ]

        dx_grid = abs(
            int(
                second["grid_x"]
            )
            - int(
                first["grid_x"]
            )
        )

        dy_grid = abs(
            int(
                second["grid_y"]
            )
            - int(
                first["grid_y"]
            )
        )

        dx_local = abs(
            float(
                second["east_m"]
            )
            - float(
                first["east_m"]
            )
        )

        dy_local = abs(
            float(
                second["north_m"]
            )
            - float(
                first["north_m"]
            )
        )

        if (
            dx_grid > 0
            and dx_local > 0
        ):
            candidates.append(
                dx_local
                / dx_grid
            )

        if (
            dy_grid > 0
            and dy_local > 0
        ):
            candidates.append(
                dy_local
                / dy_grid
            )

    if not candidates:
        raise RuntimeError(
            "Unable to infer grid "
            "resolution from "
            "planned_waypoints.csv"
        )

    return (
        sum(candidates)
        / len(candidates)
    )


def _grid_to_local(
    node: list[int]
    | tuple[int, int],
    *,
    origin: tuple[int, int],
    resolution_m: float,
) -> tuple[float, float]:
    grid_x = int(
        node[0]
    )

    grid_y = int(
        node[1]
    )

    east_m = (
        (
            grid_x
            - origin[0]
        )
        * resolution_m
    )

    north_m = (
        (
            origin[1]
            - grid_y
        )
        * resolution_m
    )

    return (
        east_m,
        north_m,
    )


def _find_event(
    events: list[dict],
    event_type: str,
) -> dict:
    for event in events:
        if (
            event.get(
                "event_type"
            )
            == event_type
        ):
            return event

    raise RuntimeError(
        f"Missing structured event: "
        f"{event_type}"
    )


def _find_advisor_record(
    records: list[dict],
) -> dict | None:
    for record in records:
        if (
            record.get(
                "event_type"
            )
            == "INCIDENT_ADVISORY"
        ):
            return record

    return None


def _mission_completed(
    actual: list[dict],
) -> bool:
    if not actual:
        return False

    last = actual[-1]

    return (
        last.get(
            "target_waypoint"
        )
        == "LANDED"
        and str(
            last.get(
                "in_air"
            )
        ).lower()
        == "false"
    )


def evaluate_dynamic_replan(
    run_dir: Path,
) -> dict:
    """
    Evaluate one structured runtime
    communication-aware replan.

    Required artifacts:
      - actual_trajectory.csv
      - planned_waypoints.csv
      - mission_summary.json
      - communication_summary.json
      - incident_events.json
      - runtime_replans.json

    No Uvicorn/backend log is required.
    """

    run_dir = Path(
        run_dir
    )

    actual = _load_csv(
        run_dir
        / "actual_trajectory.csv"
    )

    planned = _load_csv(
        run_dir
        / "planned_waypoints.csv"
    )

    mission_summary = (
        _load_json(
            run_dir
            / "mission_summary.json"
        )
    )

    communication_summary = (
        _load_json(
            run_dir
            / "communication_summary.json"
        )
    )

    incident_document = (
        _load_json(
            run_dir
            / "incident_events.json"
        )
    )

    replan_document = (
        _load_json(
            run_dir
            / "runtime_replans.json"
        )
    )

    communication_events = (
        incident_document.get(
            "communication_events",
            [],
        )
    )

    incident_records = (
        incident_document.get(
            "incident_records",
            [],
        )
    )

    replan_decisions = (
        replan_document.get(
            "replan_decisions",
            [],
        )
    )

    route_application_events = (
        replan_document.get(
            "route_application_events",
            [],
        )
    )

    if not replan_decisions:
        raise RuntimeError(
            "No structured runtime "
            "replan decision found"
        )

    if not route_application_events:
        raise RuntimeError(
            "No structured route "
            "application event found"
        )

    decision_record = (
        replan_decisions[0]
    )

    route_application = (
        route_application_events[0]
    )

    degraded = _find_event(
        communication_events,
        "COMMUNICATION_DEGRADED",
    )

    recovered = _find_event(
        communication_events,
        "COMMUNICATION_RECOVERED",
    )

    for event_name, event in (
        (
            "COMMUNICATION_DEGRADED",
            degraded,
        ),
        (
            "COMMUNICATION_RECOVERED",
            recovered,
        ),
    ):
        if (
            "timestamp_utc"
            not in event
        ):
            raise RuntimeError(
                f"{event_name} is missing "
                f"timestamp_utc. "
                f"This artifact predates "
                f"V0.7.8-B2.2."
            )

    if (
        "timestamp_utc"
        not in route_application
    ):
        raise RuntimeError(
            "Route application event "
            "is missing timestamp_utc"
        )

    degraded_time = _parse_time(
        degraded[
            "timestamp_utc"
        ]
    )

    recovered_time = _parse_time(
        recovered[
            "timestamp_utc"
        ]
    )

    route_apply_time = (
        _parse_time(
            route_application[
                "timestamp_utc"
            ]
        )
    )

    incident_to_route_apply_s = (
        route_apply_time
        - degraded_time
    ).total_seconds()

    incident_to_recovery_s = (
        recovered_time
        - degraded_time
    ).total_seconds()

    # ====================================================
    # Match structured event times to recorded trajectory
    # ====================================================

    incident_actual_index = (
        _nearest_timestamp_index(
            actual,
            degraded[
                "timestamp_utc"
            ],
        )
    )

    route_apply_index = (
        _nearest_timestamp_index(
            actual,
            route_application[
                "timestamp_utc"
            ],
        )
    )

    recovery_actual_index = (
        _nearest_timestamp_index(
            actual,
            recovered[
                "timestamp_utc"
            ],
        )
    )

    incident_actual_point = (
        _row_point(
            actual[
                incident_actual_index
            ]
        )
    )

    route_apply_point = (
        _row_point(
            actual[
                route_apply_index
            ]
        )
    )

    recovery_actual_point = (
        _row_point(
            actual[
                recovery_actual_index
            ]
        )
    )

    # ====================================================
    # Original route
    # ====================================================

    original_route = [
        (
            float(
                row["east_m"]
            ),
            float(
                row["north_m"]
            ),
        )
        for row in planned
    ]

    mission_start = (
        int(
            planned[0][
                "grid_x"
            ]
        ),
        int(
            planned[0][
                "grid_y"
            ]
        ),
    )

    resolution_m = (
        _infer_grid_resolution(
            planned
        )
    )

    # ====================================================
    # Fresh position and runtime route
    # ====================================================

    latest_position = (
        decision_record.get(
            "latest_position"
        )
        or {}
    )

    fresh_east_m = float(
        latest_position.get(
            "east_m",
            degraded[
                "east_m"
            ],
        )
    )

    fresh_north_m = float(
        latest_position.get(
            "north_m",
            degraded[
                "north_m"
            ],
        )
    )

    fresh_point = (
        fresh_east_m,
        fresh_north_m,
    )

    replan_path = (
        decision_record.get(
            "replan_path"
        )
    )

    if not replan_path:
        raise RuntimeError(
            "Structured replan decision "
            "does not contain replan_path"
        )

    replan_local_route = [
        _grid_to_local(
            node,
            origin=mission_start,
            resolution_m=(
                resolution_m
            ),
        )
        for node
        in replan_path
    ]

    # The first node is the rounded current grid.
    # RuntimeIncidentHandler intentionally skips
    # commanding the aircraft back to this point.
    replan_targets = (
        replan_local_route[1:]
    )

    original_distance_before_replan = (
        _project_distance_along_route(
            fresh_point,
            original_route,
        )
    )

    replanned_remaining_distance = (
        0.0
    )

    previous = fresh_point

    for target in replan_targets:
        replanned_remaining_distance += (
            _distance(
                previous,
                target,
            )
        )

        previous = target

    revised_total_planned_distance = (
        original_distance_before_replan
        + replanned_remaining_distance
    )

    actual_distance = float(
        mission_summary[
            "actual_distance_m"
        ]
    )

    actual_before_route_apply = (
        _trajectory_distance(
            actual,
            0,
            route_apply_index,
        )
    )

    actual_after_route_apply = (
        _trajectory_distance(
            actual,
            route_apply_index,
            len(actual) - 1,
        )
    )

    recovery_path_distance = (
        _trajectory_distance(
            actual,
            incident_actual_index,
            recovery_actual_index,
        )
    )

    # ====================================================
    # Communication improvement
    # ====================================================

    communication_change = {
        "incident_rsrp_dbm":
            float(
                degraded[
                    "rsrp_dbm"
                ]
            ),

        "recovery_rsrp_dbm":
            float(
                recovered[
                    "rsrp_dbm"
                ]
            ),

        "rsrp_improvement_db":
            (
                float(
                    recovered[
                        "rsrp_dbm"
                    ]
                )
                -
                float(
                    degraded[
                        "rsrp_dbm"
                    ]
                )
            ),

        "incident_sinr_db":
            float(
                degraded[
                    "sinr_db"
                ]
            ),

        "recovery_sinr_db":
            float(
                recovered[
                    "sinr_db"
                ]
            ),

        "sinr_improvement_db":
            (
                float(
                    recovered[
                        "sinr_db"
                    ]
                )
                -
                float(
                    degraded[
                        "sinr_db"
                    ]
                )
            ),

        "incident_coverage_score":
            float(
                degraded[
                    "coverage_score"
                ]
            ),

        "recovery_coverage_score":
            float(
                recovered[
                    "coverage_score"
                ]
            ),

        "coverage_score_improvement":
            (
                float(
                    recovered[
                        "coverage_score"
                    ]
                )
                -
                float(
                    degraded[
                        "coverage_score"
                    ]
                )
            ),
    }

    # ====================================================
    # Fast deterministic decision
    # ====================================================

    decision = (
        decision_record.get(
            "decision"
        )
        or {}
    )

    fast_policy = {
        "decision":
            decision.get(
                "decision"
            ),

        "selected_planner":
            decision.get(
                "selected_planner"
            ),

        "reason":
            decision.get(
                "reason"
            ),

        "decision_source":
            decision_record.get(
                "decision_source"
            ),

        "total_latency_s":
            decision_record.get(
                "fast_decision_latency_s"
            ),

        "comparison":
            decision_record.get(
                "comparison"
            ),
    }

    advisor_record = (
        _find_advisor_record(
            incident_records
        )
    )

    advisor = None

    if advisor_record is not None:
        advisor = {
            "status":
                advisor_record.get(
                    "action"
                ),

            "latency_s":
                advisor_record.get(
                    "background_latency_s"
                ),

            "result":
                advisor_record.get(
                    "result"
                ),
        }

    # ====================================================
    # Timing / movement
    # ====================================================

    route_switch_displacement = (
        _distance(
            (
                float(
                    degraded[
                        "east_m"
                    ]
                ),
                float(
                    degraded[
                        "north_m"
                    ]
                ),
            ),
            route_apply_point,
        )
    )

    recovery_path_distance = (
        _trajectory_distance(
            actual,
            incident_actual_index,
            recovery_actual_index,
        )
    )

    degraded_elapsed_s = (
        degraded.get(
            "elapsed_s"
        )
    )

    recovered_elapsed_s = (
        recovered.get(
            "elapsed_s"
        )
    )

    route_apply_elapsed_s = None

    if (
        degraded_elapsed_s
        is not None
    ):
        route_apply_elapsed_s = (
            float(
                degraded_elapsed_s
            )
            + incident_to_route_apply_s
        )

    # ====================================================
    # Summary
    # ====================================================

    summary = {
        "schema_version":
            "2.0",

        "mission_status":
            (
                "COMPLETED"
                if _mission_completed(
                    actual
                )
                else "UNKNOWN"
            ),

        "dynamic_replan_detected":
            True,

        "artifact_source":
            "STRUCTURED_RUNTIME_ARTIFACTS",

        "log_file_required":
            False,

        "fast_policy":
            fast_policy,

        "advisor":
            advisor,

        "incident": {
            "timestamp_utc":
                degraded[
                    "timestamp_utc"
                ],

            "elapsed_s":
                degraded_elapsed_s,

            "east_m":
                float(
                    degraded[
                        "east_m"
                    ]
                ),

            "north_m":
                float(
                    degraded[
                        "north_m"
                    ]
                ),

            "rsrp_dbm":
                float(
                    degraded[
                        "rsrp_dbm"
                    ]
                ),

            "sinr_db":
                float(
                    degraded[
                        "sinr_db"
                    ]
                ),

            "coverage_score":
                float(
                    degraded[
                        "coverage_score"
                    ]
                ),
        },

        "route_application": {
            "timestamp_utc":
                route_application[
                    "timestamp_utc"
                ],

            "elapsed_s":
                route_apply_elapsed_s,

            "incident_to_route_apply_s":
                incident_to_route_apply_s,

            "east_m":
                route_apply_point[0],

            "north_m":
                route_apply_point[1],

            "incident_to_route_apply_displacement_m":
                route_switch_displacement,

            "fresh_position_east_m":
                fresh_east_m,

            "fresh_position_north_m":
                fresh_north_m,

            "incident_grid":
                decision_record.get(
                    "incident_grid"
                ),

            "replan_current_grid":
                decision_record.get(
                    "replan_current_grid"
                ),

            "incident_to_fresh_drift_m":
                decision_record.get(
                    "decision_position_drift_m"
                ),
        },

        "recovery": {
            "timestamp_utc":
                recovered[
                    "timestamp_utc"
                ],

            "elapsed_s":
                recovered_elapsed_s,

            "east_m":
                float(
                    recovered[
                        "east_m"
                    ]
                ),

            "north_m":
                float(
                    recovered[
                        "north_m"
                    ]
                ),

            "incident_to_recovery_s":
                incident_to_recovery_s,

            "incident_to_recovery_path_m":
                recovery_path_distance,
        },

        "distance_evaluation": {
            "grid_resolution_m":
                resolution_m,

            "original_planned_distance_m":
                float(
                    mission_summary[
                        "planned_distance_m"
                    ]
                ),

            "original_reference_distance_before_replan_m":
                original_distance_before_replan,

            "replanned_remaining_distance_m":
                replanned_remaining_distance,

            "revised_total_planned_distance_m":
                revised_total_planned_distance,

            "actual_distance_m":
                actual_distance,

            "actual_distance_before_route_apply_m":
                actual_before_route_apply,

            "actual_distance_after_route_apply_m":
                actual_after_route_apply,

            "dynamic_extra_distance_m":
                (
                    actual_distance
                    - revised_total_planned_distance
                ),

            "dynamic_flight_efficiency":
                (
                    revised_total_planned_distance
                    / actual_distance
                    if actual_distance > 0
                    else None
                ),

            "legacy_static_efficiency":
                mission_summary.get(
                    "flight_efficiency"
                ),
        },

        "communication_change":
            communication_change,

        "whole_mission_communication":
            communication_summary,

        "replan_path_grid":
            replan_path,

        "replan_targets": [
            {
                "index":
                    index,

                "grid_x":
                    int(
                        replan_path[index][0]
                    ),

                "grid_y":
                    int(
                        replan_path[index][1]
                    ),

                "east_m":
                    replan_local_route[
                        index
                    ][0],

                "north_m":
                    replan_local_route[
                        index
                    ][1],
            }
            for index in range(
                1,
                len(
                    replan_path
                ),
            )
        ],
    }

    # ====================================================
    # JSON artifact
    # ====================================================

    output_json = (
        run_dir
        / "dynamic_replan_evaluation.json"
    )

    output_json.write_text(
        json.dumps(
            summary,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    # ====================================================
    # Revised route CSV
    # ====================================================

    route_csv = (
        run_dir
        / "dynamic_route_waypoints.csv"
    )

    altitude_m = (
        incident_document
        .get(
            "mission",
            {},
        )
        .get(
            "altitude_m"
        )
    )

    with route_csv.open(
        "w",
        encoding="utf-8",
        newline="",
    ) as file:
        fieldnames = [
            "waypoint_id",
            "grid_x",
            "grid_y",
            "east_m",
            "north_m",
            "altitude_m",
        ]

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        current_grid = (
            decision_record.get(
                "replan_current_grid"
            )
            or replan_path[0]
        )

        writer.writerow(
            {
                "waypoint_id":
                    "REPLAN_CURRENT",

                "grid_x":
                    current_grid[0],

                "grid_y":
                    current_grid[1],

                "east_m":
                    fresh_east_m,

                "north_m":
                    fresh_north_m,

                "altitude_m":
                    altitude_m,
            }
        )

        for index in range(
            1,
            len(
                replan_path
            ),
        ):
            point = (
                replan_local_route[
                    index
                ]
            )

            writer.writerow(
                {
                    "waypoint_id":
                        f"R1_WP{index}",

                    "grid_x":
                        replan_path[
                            index
                        ][0],

                    "grid_y":
                        replan_path[
                            index
                        ][1],

                    "east_m":
                        point[0],

                    "north_m":
                        point[1],

                    "altitude_m":
                        altitude_m,
                }
            )

    # ====================================================
    # Plot
    # ====================================================

    actual_east = [
        float(
            row["east_m"]
        )
        for row in actual
    ]

    actual_north = [
        float(
            row["north_m"]
        )
        for row in actual
    ]

    original_east = [
        point[0]
        for point
        in original_route
    ]

    original_north = [
        point[1]
        for point
        in original_route
    ]

    revised_plot_route = [
        fresh_point,
        *replan_targets,
    ]

    revised_east = [
        point[0]
        for point
        in revised_plot_route
    ]

    revised_north = [
        point[1]
        for point
        in revised_plot_route
    ]

    plt.figure(
        figsize=(9, 7)
    )

    plt.plot(
        original_east,
        original_north,
        marker="o",
        label="Original planned route",
    )

    plt.plot(
        revised_east,
        revised_north,
        marker="o",
        label="Runtime revised route",
    )

    plt.plot(
        actual_east,
        actual_north,
        label="Actual trajectory",
    )

    plt.scatter(
        [
            float(
                degraded[
                    "east_m"
                ]
            )
        ],
        [
            float(
                degraded[
                    "north_m"
                ]
            )
        ],
        marker="x",
        s=100,
        label="Communication degraded",
    )

    plt.scatter(
        [
            route_apply_point[0]
        ],
        [
            route_apply_point[1]
        ],
        marker="s",
        s=70,
        label="Route applied",
    )

    plt.scatter(
        [
            float(
                recovered[
                    "east_m"
                ]
            )
        ],
        [
            float(
                recovered[
                    "north_m"
                ]
            )
        ],
        marker="^",
        s=90,
        label="Communication recovered",
    )

    plt.xlabel(
        "East (m)"
    )

    plt.ylabel(
        "North (m)"
    )

    plt.title(
        "Dynamic Communication-Aware Replanning"
    )

    plt.axis(
        "equal"
    )

    plt.grid(
        True,
        alpha=0.3,
    )

    plt.legend()

    plt.tight_layout()

    output_png = (
        run_dir
        / "dynamic_trajectory_comparison.png"
    )

    plt.savefig(
        output_png,
        dpi=180,
    )

    plt.close()

    print(
        "[DYNAMIC EVAL] "
        "Structured artifacts: PASS"
    )

    print(
        "[DYNAMIC EVAL] "
        "Log file required: False"
    )

    print(
        "[DYNAMIC EVAL] JSON:",
        output_json,
    )

    print(
        "[DYNAMIC EVAL] Route:",
        route_csv,
    )

    print(
        "[DYNAMIC EVAL] Plot:",
        output_png,
    )

    return summary


def evaluate_dynamic_replan_if_available(
    run_dir: Path,
) -> dict | None:
    """
    Run dynamic evaluation only when a
    real runtime route replacement exists.

    Normal missions are silently skipped.
    """

    run_dir = Path(
        run_dir
    )

    replan_artifact = (
        run_dir
        / "runtime_replans.json"
    )

    if not replan_artifact.exists():
        return None

    document = _load_json(
        replan_artifact
    )

    replan_decisions = (
        document.get(
            "replan_decisions",
            [],
        )
    )

    route_application_events = (
        document.get(
            "route_application_events",
            [],
        )
    )

    if (
        not replan_decisions
        or not route_application_events
    ):
        return None

    required = [
        "actual_trajectory.csv",
        "planned_waypoints.csv",
        "mission_summary.json",
        "communication_summary.json",
        "incident_events.json",
        "runtime_replans.json",
    ]

    missing = [
        name
        for name in required
        if not (
            run_dir
            / name
        ).exists()
    ]

    if missing:
        raise RuntimeError(
            "Dynamic replan detected but "
            "evaluation artifacts are missing: "
            + ", ".join(
                missing
            )
        )

    return evaluate_dynamic_replan(
        run_dir
    )
