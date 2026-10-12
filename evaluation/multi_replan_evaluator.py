from __future__ import annotations

import json
import math

from pathlib import Path
from statistics import mean

from evaluation.dynamic_replan_evaluator import (
    _infer_grid_resolution,
    _load_csv,
    _load_json,
    _mission_completed,
    _nearest_timestamp_index,
    _parse_time,
    _project_distance_along_route,
    _row_point,
    _trajectory_distance,
    _grid_to_local,
)


def _distance(
    first: tuple[float, float],
    second: tuple[float, float],
) -> float:
    return math.hypot(
        second[0] - first[0],
        second[1] - first[1],
    )


def _polyline_length(
    points: list[
        tuple[float, float]
    ],
) -> float:
    total = 0.0

    for index in range(
        1,
        len(points),
    ):
        total += _distance(
            points[index - 1],
            points[index],
        )

    return total


def _find_matching_degradation(
    *,
    decision: dict,
    communication_events: list[dict],
    start_index: int,
) -> tuple[int, dict]:
    """
    Match one REPLAN_QUEUED record to its
    originating COMMUNICATION_DEGRADED event.

    The current structured runtime schema does
    not yet store the incident timestamp inside
    the decision record, so matching uses the
    incident position while preserving event
    order.
    """

    context = (
        decision.get(
            "context",
            {},
        )
    )

    target_east = float(
        context[
            "east_m"
        ]
    )

    target_north = float(
        context[
            "north_m"
        ]
    )

    candidates = []

    for index in range(
        start_index,
        len(
            communication_events
        ),
    ):
        event = (
            communication_events[
                index
            ]
        )

        if (
            event.get(
                "event_type"
            )
            != "COMMUNICATION_DEGRADED"
        ):
            continue

        distance_m = _distance(
            (
                target_east,
                target_north,
            ),
            (
                float(
                    event["east_m"]
                ),
                float(
                    event["north_m"]
                ),
            ),
        )

        candidates.append(
            (
                distance_m,
                index,
                event,
            )
        )

    if not candidates:
        raise RuntimeError(
            "Unable to match replan decision "
            "to a degradation event"
        )

    (
        distance_m,
        index,
        event,
    ) = min(
        candidates,
        key=lambda item: item[0],
    )

    if distance_m > 2.0:
        raise RuntimeError(
            "Matched degradation event is "
            f"{distance_m:.2f} m away from "
            "decision context"
        )

    return (
        index,
        event,
    )


def _find_recovery_after(
    *,
    communication_events: list[dict],
    degradation_index: int,
) -> dict | None:
    """
    Return the recovery belonging to one
    degradation episode.

    Stop if another degradation begins first.
    """

    for index in range(
        degradation_index + 1,
        len(
            communication_events
        ),
    ):
        event = (
            communication_events[
                index
            ]
        )

        event_type = (
            event.get(
                "event_type"
            )
        )

        if (
            event_type
            == "COMMUNICATION_RECOVERED"
        ):
            return event

        if (
            event_type
            == "COMMUNICATION_DEGRADED"
        ):
            return None

    return None


def _build_apply_event_map(
    route_events: list[dict],
) -> dict[int, dict]:
    result = {}

    for event in route_events:
        metadata = (
            event.get(
                "metadata",
                {},
            )
        )

        replan_index = (
            metadata.get(
                "replan_index"
            )
        )

        if replan_index is None:
            continue

        result[
            int(
                replan_index
            )
        ] = event

    return result


def _communication_change(
    degradation: dict,
    recovery: dict | None,
) -> dict | None:
    if recovery is None:
        return None

    incident_rsrp = float(
        degradation[
            "rsrp_dbm"
        ]
    )

    recovery_rsrp = float(
        recovery[
            "rsrp_dbm"
        ]
    )

    incident_sinr = float(
        degradation[
            "sinr_db"
        ]
    )

    recovery_sinr = float(
        recovery[
            "sinr_db"
        ]
    )

    incident_score = float(
        degradation[
            "coverage_score"
        ]
    )

    recovery_score = float(
        recovery[
            "coverage_score"
        ]
    )

    return {
        "incident_rsrp_dbm":
            incident_rsrp,

        "recovery_rsrp_dbm":
            recovery_rsrp,

        "rsrp_improvement_db":
            recovery_rsrp
            - incident_rsrp,

        "incident_sinr_db":
            incident_sinr,

        "recovery_sinr_db":
            recovery_sinr,

        "sinr_improvement_db":
            recovery_sinr
            - incident_sinr,

        "incident_coverage_score":
            incident_score,

        "recovery_coverage_score":
            recovery_score,

        "coverage_score_improvement":
            recovery_score
            - incident_score,
    }


def evaluate_multi_replan(
    run_dir: Path,
) -> dict:
    """
    Evaluate a mission containing one or more
    applied runtime replans.

    The output models each degradation/replan/
    recovery sequence as one episode and then
    calculates mission-level aggregate metrics.
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

    mission_summary = _load_json(
        run_dir
        / "mission_summary.json"
    )

    incident_document = _load_json(
        run_dir
        / "incident_events.json"
    )

    replan_document = _load_json(
        run_dir
        / "runtime_replans.json"
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

    route_events = (
        replan_document.get(
            "route_application_events",
            [],
        )
    )

    if not replan_decisions:
        raise RuntimeError(
            "No runtime replan decisions found"
        )

    if not route_events:
        raise RuntimeError(
            "No route application events found"
        )

    if (
        len(replan_decisions)
        != len(route_events)
    ):
        raise RuntimeError(
            "Replan decision/application count "
            "mismatch: "
            f"{len(replan_decisions)} decisions, "
            f"{len(route_events)} applications"
        )

    advisors = [
        record
        for record
        in incident_records
        if (
            record.get(
                "event_type"
            )
            == "INCIDENT_ADVISORY"
        )
    ]

    apply_event_map = (
        _build_apply_event_map(
            route_events
        )
    )

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

    episodes = []

    degradation_search_index = 0

    for episode_number, decision_record in enumerate(
        replan_decisions,
        start=1,
    ):
        (
            degradation_index,
            degradation,
        ) = _find_matching_degradation(
            decision=decision_record,
            communication_events=(
                communication_events
            ),
            start_index=(
                degradation_search_index
            ),
        )

        degradation_search_index = (
            degradation_index + 1
        )

        recovery = (
            _find_recovery_after(
                communication_events=(
                    communication_events
                ),
                degradation_index=(
                    degradation_index
                ),
            )
        )

        route_application = (
            apply_event_map.get(
                episode_number
            )
        )

        if route_application is None:
            route_application = (
                route_events[
                    episode_number - 1
                ]
            )

        degradation_time = (
            _parse_time(
                degradation[
                    "timestamp_utc"
                ]
            )
        )

        application_time = (
            _parse_time(
                route_application[
                    "timestamp_utc"
                ]
            )
        )

        incident_to_apply_s = (
            application_time
            - degradation_time
        ).total_seconds()

        latest_position = (
            decision_record.get(
                "latest_position",
                {},
            )
        )

        fresh_point = (
            float(
                latest_position.get(
                    "east_m",
                    degradation[
                        "east_m"
                    ],
                )
            ),
            float(
                latest_position.get(
                    "north_m",
                    degradation[
                        "north_m"
                    ],
                )
            ),
        )

        replan_path = (
            decision_record.get(
                "replan_path"
            )
        )

        if not replan_path:
            raise RuntimeError(
                f"Replan {episode_number} "
                "does not contain replan_path"
            )

        local_route = [
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

        route_targets = (
            local_route[1:]
        )

        commanded_route = [
            fresh_point,
            *route_targets,
        ]

        planned_remaining_m = (
            _polyline_length(
                commanded_route
            )
        )

        degradation_actual_index = (
            _nearest_timestamp_index(
                actual,
                degradation[
                    "timestamp_utc"
                ],
            )
        )

        apply_actual_index = (
            _nearest_timestamp_index(
                actual,
                route_application[
                    "timestamp_utc"
                ],
            )
        )

        apply_actual_point = (
            _row_point(
                actual[
                    apply_actual_index
                ]
            )
        )

        recovery_metrics = None

        if recovery is not None:
            recovery_time = (
                _parse_time(
                    recovery[
                        "timestamp_utc"
                    ]
                )
            )

            recovery_actual_index = (
                _nearest_timestamp_index(
                    actual,
                    recovery[
                        "timestamp_utc"
                    ],
                )
            )

            recovery_metrics = {
                "timestamp_utc":
                    recovery[
                        "timestamp_utc"
                    ],

                "elapsed_s":
                    recovery.get(
                        "elapsed_s"
                    ),

                "east_m":
                    float(
                        recovery[
                            "east_m"
                        ]
                    ),

                "north_m":
                    float(
                        recovery[
                            "north_m"
                        ]
                    ),

                "incident_to_recovery_s":
                    (
                        recovery_time
                        - degradation_time
                    ).total_seconds(),

                "incident_to_recovery_path_m":
                    _trajectory_distance(
                        actual,
                        degradation_actual_index,
                        recovery_actual_index,
                    ),
            }

        decision = (
            decision_record.get(
                "decision",
                {},
            )
        )

        advisor = None

        if (
            episode_number
            <= len(advisors)
        ):
            advisor_record = (
                advisors[
                    episode_number - 1
                ]
            )

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

        episodes.append(
            {
                "episode_index":
                    episode_number,

                "degradation": {
                    "timestamp_utc":
                        degradation[
                            "timestamp_utc"
                        ],

                    "elapsed_s":
                        degradation.get(
                            "elapsed_s"
                        ),

                    "east_m":
                        float(
                            degradation[
                                "east_m"
                            ]
                        ),

                    "north_m":
                        float(
                            degradation[
                                "north_m"
                            ]
                        ),

                    "rsrp_dbm":
                        float(
                            degradation[
                                "rsrp_dbm"
                            ]
                        ),

                    "sinr_db":
                        float(
                            degradation[
                                "sinr_db"
                            ]
                        ),

                    "coverage_score":
                        float(
                            degradation[
                                "coverage_score"
                            ]
                        ),
                },

                "fast_policy": {
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

                    "triggered_rules":
                        decision.get(
                            "triggered_rules",
                            [],
                        ),

                    "metrics":
                        decision.get(
                            "metrics",
                            {},
                        ),

                    "decision_source":
                        decision_record.get(
                            "decision_source"
                        ),

                    "compare_latency_s":
                        decision_record.get(
                            "compare_latency_s"
                        ),

                    "policy_latency_s":
                        decision_record.get(
                            "policy_latency_s"
                        ),

                    "total_latency_s":
                        decision_record.get(
                            "fast_decision_latency_s"
                        ),
                },

                "route_application": {
                    "timestamp_utc":
                        route_application[
                            "timestamp_utc"
                        ],

                    "incident_to_route_apply_s":
                        incident_to_apply_s,

                    "east_m":
                        apply_actual_point[0],

                    "north_m":
                        apply_actual_point[1],

                    "replan_index":
                        (
                            route_application
                            .get(
                                "metadata",
                                {},
                            )
                            .get(
                                "replan_index"
                            )
                        ),

                    "waypoint_count":
                        (
                            route_application
                            .get(
                                "metadata",
                                {},
                            )
                            .get(
                                "waypoint_count"
                            )
                        ),
                },

                "fresh_position": {
                    "east_m":
                        fresh_point[0],

                    "north_m":
                        fresh_point[1],

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

                "route": {
                    "replan_path_grid":
                        replan_path,

                    "planned_remaining_distance_m":
                        planned_remaining_m,

                    "targets": [
                        {
                            "index":
                                index,

                            "grid_x":
                                int(
                                    replan_path[
                                        index
                                    ][0]
                                ),

                            "grid_y":
                                int(
                                    replan_path[
                                        index
                                    ][1]
                                ),

                            "east_m":
                                local_route[
                                    index
                                ][0],

                            "north_m":
                                local_route[
                                    index
                                ][1],
                        }
                        for index
                        in range(
                            1,
                            len(
                                replan_path
                            ),
                        )
                    ],
                },

                "recovery":
                    recovery_metrics,

                "communication_change":
                    _communication_change(
                        degradation,
                        recovery,
                    ),

                "advisor":
                    advisor,
            }
        )

    # ====================================================
    # Reconstruct the effective revised planned distance.
    #
    # For every runtime switch:
    #   1. measure planned progress on the currently
    #      active route up to the fresh switch position;
    #   2. replace the remaining route with the newly
    #      commanded runtime route.
    #
    # After the final switch, add the final remaining
    # planned route distance to the goal.
    # ====================================================

    active_route = list(
        original_route
    )

    revised_planned_distance = (
        0.0
    )

    for episode in episodes:
        fresh = (
            episode[
                "fresh_position"
            ][
                "east_m"
            ],
            episode[
                "fresh_position"
            ][
                "north_m"
            ],
        )

        progress_on_active_route = (
            _project_distance_along_route(
                fresh,
                active_route,
            )
        )

        episode[
            "route"
        ][
            "planned_progress_before_switch_m"
        ] = progress_on_active_route

        revised_planned_distance += (
            progress_on_active_route
        )

        targets = [
            (
                float(
                    item[
                        "east_m"
                    ]
                ),
                float(
                    item[
                        "north_m"
                    ]
                ),
            )
            for item
            in episode[
                "route"
            ][
                "targets"
            ]
        ]

        active_route = [
            fresh,
            *targets,
        ]

    final_remaining_distance = (
        _polyline_length(
            active_route
        )
    )

    revised_planned_distance += (
        final_remaining_distance
    )

    actual_distance = float(
        mission_summary[
            "actual_distance_m"
        ]
    )

    fast_latencies = [
        float(
            episode[
                "fast_policy"
            ][
                "total_latency_s"
            ]
        )
        for episode
        in episodes
        if (
            episode[
                "fast_policy"
            ][
                "total_latency_s"
            ]
            is not None
        )
    ]

    apply_latencies = [
        float(
            episode[
                "route_application"
            ][
                "incident_to_route_apply_s"
            ]
        )
        for episode
        in episodes
    ]

    recovery_times = [
        float(
            episode[
                "recovery"
            ][
                "incident_to_recovery_s"
            ]
        )
        for episode
        in episodes
        if (
            episode[
                "recovery"
            ]
            is not None
        )
    ]

    recovery_distances = [
        float(
            episode[
                "recovery"
            ][
                "incident_to_recovery_path_m"
            ]
        )
        for episode
        in episodes
        if (
            episode[
                "recovery"
            ]
            is not None
        )
    ]

    advisor_completed = sum(
        1
        for episode
        in episodes
        if (
            episode.get(
                "advisor"
            )
            is not None
            and episode[
                "advisor"
            ].get(
                "status"
            )
            == "ADVISOR_COMPLETED"
        )
    )

    advisor_failed = sum(
        1
        for episode
        in episodes
        if (
            episode.get(
                "advisor"
            )
            is not None
            and episode[
                "advisor"
            ].get(
                "status"
            )
            in {
                "ADVISOR_FAILED",
                "ADVISOR_TIMEOUT",
            }
        )
    )

    result = {
        "schema_version":
            "3.0",

        "mission_status":
            (
                "COMPLETED"
                if _mission_completed(
                    actual
                )
                else "UNKNOWN"
            ),

        "artifact_source":
            "STRUCTURED_RUNTIME_ARTIFACTS",

        "evaluation_mode":
            "MULTI_REPLAN",

        "episode_count":
            len(
                episodes
            ),

        "episodes":
            episodes,

        "overall": {
            "replan_count":
                len(
                    episodes
                ),

            "recovery_count":
                len(
                    recovery_times
                ),

            "original_planned_distance_m":
                float(
                    mission_summary[
                        "planned_distance_m"
                    ]
                ),

            "revised_total_planned_distance_m":
                revised_planned_distance,

            "final_remaining_planned_distance_m":
                final_remaining_distance,

            "actual_distance_m":
                actual_distance,

            "dynamic_extra_distance_m":
                (
                    actual_distance
                    - revised_planned_distance
                ),

            "dynamic_flight_efficiency":
                (
                    revised_planned_distance
                    / actual_distance
                    if actual_distance > 0
                    else None
                ),

            "legacy_static_efficiency":
                mission_summary.get(
                    "flight_efficiency"
                ),

            "mean_fast_decision_latency_s":
                (
                    mean(
                        fast_latencies
                    )
                    if fast_latencies
                    else None
                ),

            "max_fast_decision_latency_s":
                (
                    max(
                        fast_latencies
                    )
                    if fast_latencies
                    else None
                ),

            "mean_incident_to_route_apply_s":
                (
                    mean(
                        apply_latencies
                    )
                    if apply_latencies
                    else None
                ),

            "max_incident_to_route_apply_s":
                (
                    max(
                        apply_latencies
                    )
                    if apply_latencies
                    else None
                ),

            "mean_recovery_time_s":
                (
                    mean(
                        recovery_times
                    )
                    if recovery_times
                    else None
                ),

            "max_recovery_time_s":
                (
                    max(
                        recovery_times
                    )
                    if recovery_times
                    else None
                ),

            "mean_recovery_path_m":
                (
                    mean(
                        recovery_distances
                    )
                    if recovery_distances
                    else None
                ),

            "advisor_completed_count":
                advisor_completed,

            "advisor_failed_or_timeout_count":
                advisor_failed,
        },
    }

    output_path = (
        run_dir
        / "multi_replan_evaluation.json"
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "[MULTI REPLAN EVAL] "
        f"Episodes: {len(episodes)}"
    )

    for episode in episodes:
        print(
            "[MULTI REPLAN EVAL] "
            f"Episode "
            f"{episode['episode_index']}: "
            f"decision="
            f"{episode['fast_policy']['decision']}, "
            f"decision_latency="
            f"{episode['fast_policy']['total_latency_s'] * 1000:.3f} ms, "
            f"apply_latency="
            f"{episode['route_application']['incident_to_route_apply_s'] * 1000:.3f} ms"
        )

        if (
            episode[
                "recovery"
            ]
            is not None
        ):
            print(
                "[MULTI REPLAN EVAL] "
                f"Episode "
                f"{episode['episode_index']}: "
                f"recovery="
                f"{episode['recovery']['incident_to_recovery_s']:.3f} s, "
                f"path="
                f"{episode['recovery']['incident_to_recovery_path_m']:.2f} m"
            )

    print(
        "[MULTI REPLAN EVAL] "
        "Revised planned distance: "
        f"{revised_planned_distance:.2f} m"
    )

    print(
        "[MULTI REPLAN EVAL] "
        "Actual distance: "
        f"{actual_distance:.2f} m"
    )

    print(
        "[MULTI REPLAN EVAL] "
        "Dynamic efficiency: "
        f"{result['overall']['dynamic_flight_efficiency'] * 100:.2f}%"
    )

    print(
        "[MULTI REPLAN EVAL] "
        "Output:",
        output_path,
    )

    return result


def evaluate_multi_replan_if_available(
    run_dir: Path,
) -> dict | None:
    """
    Run multi-replan evaluation only when a
    mission contains at least two applied
    runtime replans.

    Returns None for normal or single-replan
    missions.
    """

    run_dir = Path(
        run_dir
    )

    runtime_path = (
        run_dir
        / "runtime_replans.json"
    )

    if not runtime_path.exists():
        return None

    try:
        document = _load_json(
            runtime_path
        )
    except Exception:
        return None

    decisions = (
        document.get(
            "replan_decisions",
            [],
        )
    )

    applications = (
        document.get(
            "route_application_events",
            [],
        )
    )

    applied_decisions = [
        record
        for record
        in decisions
        if (
            record.get(
                "action"
            )
            == "REPLAN_QUEUED"
        )
    ]

    applied_events = [
        event
        for event
        in applications
        if (
            event.get(
                "event_type"
            )
            == "RUNTIME_ROUTE_REPLACEMENT_APPLIED"
        )
    ]

    if (
        len(applied_decisions) < 2
        or len(applied_events) < 2
    ):
        return None

    return evaluate_multi_replan(
        run_dir
    )
