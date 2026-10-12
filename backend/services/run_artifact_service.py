import json

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path


PROJECT_ROOT = (
    Path(__file__)
    .resolve()
    .parents[2]
)

RUNS_ROOT = (
    PROJECT_ROOT
    / "outputs"
    / "runs"
)


SUMMARY_ARTIFACTS = (
    "mission_summary.json",
    "communication_summary.json",
    "dynamic_replan_evaluation.json",
    "multi_replan_evaluation.json",
    "rag_advisor_evaluation.json",
)


def _utc_iso_from_timestamp(
    timestamp: float,
) -> str:
    return (
        datetime.fromtimestamp(
            timestamp,
            tz=timezone.utc,
        )
        .isoformat()
    )


def _read_json_if_exists(
    path: Path,
):
    if not path.is_file():
        return None

    try:
        return json.loads(
            path.read_text(
                encoding="utf-8"
            )
        )

    except (
        json.JSONDecodeError,
        OSError,
    ):
        return None


def _resolve_run_dir(
    run_id: str,
) -> Path:
    if (
        not run_id
        or "/" in run_id
        or "\\" in run_id
        or run_id in {".", ".."}
    ):
        raise FileNotFoundError(
            run_id
        )

    root = RUNS_ROOT.resolve()

    run_dir = (
        RUNS_ROOT
        / run_id
    ).resolve()

    # Runs must be direct children of
    # outputs/runs. This also prevents
    # path traversal outside that directory.
    if run_dir.parent != root:
        raise FileNotFoundError(
            run_id
        )

    if not run_dir.is_dir():
        raise FileNotFoundError(
            run_id
        )

    return run_dir


def _extract_mission_id(
    run_dir: Path,
    incident_document=None,
    rag_document=None,
) -> str | None:
    for document in (
        incident_document,
        rag_document,
    ):
        if isinstance(
            document,
            dict,
        ):
            mission_id = (
                document.get(
                    "mission_id"
                )
            )

            if mission_id:
                return str(
                    mission_id
                )

    name = run_dir.name

    marker_index = (
        name.find(
            "mission_"
        )
    )

    if marker_index >= 0:
        return name[
            marker_index:
        ]

    return None


def _artifact_manifest(
    run_dir: Path,
) -> list[dict]:
    artifacts = []

    for path in sorted(
        run_dir.iterdir(),
        key=lambda item: item.name,
    ):
        if not path.is_file():
            continue

        stat = path.stat()

        artifacts.append(
            {
                "name":
                    path.name,

                "size_bytes":
                    stat.st_size,

                "modified_at_utc":
                    _utc_iso_from_timestamp(
                        stat.st_mtime
                    ),
            }
        )

    return artifacts


def _count_runtime_records(
    incident_document,
    replan_document,
) -> dict:
    incident_records = []

    if isinstance(
        incident_document,
        dict,
    ):
        incident_records = (
            incident_document.get(
                "incident_records",
                [],
            )
            or []
        )

    advisor_count = sum(
        1
        for record in incident_records
        if (
            record.get(
                "event_type"
            )
            == "INCIDENT_ADVISORY"
        )
    )

    replan_decisions = []

    route_application_events = []

    if isinstance(
        replan_document,
        dict,
    ):
        replan_decisions = (
            replan_document.get(
                "replan_decisions",
                [],
            )
            or []
        )

        route_application_events = (
            replan_document.get(
                "route_application_events",
                [],
            )
            or []
        )

    return {
        "incident_count":
            len(
                incident_records
            ),

        "advisor_count":
            advisor_count,

        "replan_decision_count":
            len(
                replan_decisions
            ),

        "replan_count":
            len(
                route_application_events
            ),
    }


def _build_run_summary(
    run_dir: Path,
) -> dict:
    mission_summary = (
        _read_json_if_exists(
            run_dir
            / "mission_summary.json"
        )
        or {}
    )

    communication_summary = (
        _read_json_if_exists(
            run_dir
            / "communication_summary.json"
        )
        or {}
    )

    incident_document = (
        _read_json_if_exists(
            run_dir
            / "incident_events.json"
        )
        or {}
    )

    replan_document = (
        _read_json_if_exists(
            run_dir
            / "runtime_replans.json"
        )
        or {}
    )

    rag_document = (
        _read_json_if_exists(
            run_dir
            / "rag_advisor_evaluation.json"
        )
        or {}
    )

    counts = (
        _count_runtime_records(
            incident_document,
            replan_document,
        )
    )

    stat = run_dir.stat()

    artifact_status = (
        "COMPLETE"
        if (
            (
                run_dir
                / "mission_summary.json"
            ).is_file()
            and (
                run_dir
                / "actual_trajectory.csv"
            ).is_file()
        )
        else "PARTIAL"
    )

    return {
        "run_id":
            run_dir.name,

        "mission_id":
            _extract_mission_id(
                run_dir,
                incident_document,
                rag_document,
            ),

        "artifact_status":
            artifact_status,

        "updated_at_utc":
            _utc_iso_from_timestamp(
                stat.st_mtime
            ),

        "planned_distance_m":
            mission_summary.get(
                "planned_distance_m"
            ),

        "actual_distance_m":
            mission_summary.get(
                "actual_distance_m"
            ),

        "mission_duration_s":
            mission_summary.get(
                "mission_duration_s"
            ),

        "flight_efficiency":
            mission_summary.get(
                "flight_efficiency"
            ),

        "mean_rsrp_dbm":
            communication_summary.get(
                "mean_rsrp_dbm"
            ),

        "min_rsrp_dbm":
            communication_summary.get(
                "min_rsrp_dbm"
            ),

        "mean_sinr_db":
            communication_summary.get(
                "mean_sinr_db"
            ),

        "min_sinr_db":
            communication_summary.get(
                "min_sinr_db"
            ),

        "mean_coverage_score":
            communication_summary.get(
                "mean_coverage_score"
            ),

        "min_coverage_score":
            communication_summary.get(
                "min_coverage_score"
            ),

        **counts,
    }


def list_runs() -> list[dict]:
    if not RUNS_ROOT.is_dir():
        return []

    run_dirs = [
        path
        for path in RUNS_ROOT.iterdir()
        if path.is_dir()
    ]

    run_dirs.sort(
        key=lambda path: (
            path.stat().st_mtime
        ),
        reverse=True,
    )

    return [
        _build_run_summary(
            run_dir
        )
        for run_dir in run_dirs
    ]


def get_run_detail(
    run_id: str,
) -> dict:
    run_dir = _resolve_run_dir(
        run_id
    )

    summary = (
        _build_run_summary(
            run_dir
        )
    )

    summaries = {}

    for artifact_name in (
        SUMMARY_ARTIFACTS
    ):
        document = (
            _read_json_if_exists(
                run_dir
                / artifact_name
            )
        )

        key = (
            artifact_name
            .removesuffix(
                ".json"
            )
        )

        summaries[key] = (
            document
        )

    return {
        "run":
            summary,

        "summaries":
            summaries,

        "artifacts":
            _artifact_manifest(
                run_dir
            ),
    }


def get_run_trajectory(
    run_id: str,
    stride: int = 1,
) -> dict:
    """
    Read trajectory_communication.csv for one persisted run.

    stride controls down-sampling:
        stride=1 -> return every point
        stride=5 -> return every fifth point
    """

    import csv

    if stride < 1:
        raise ValueError(
            "stride must be greater than or equal to 1"
        )

    run_dir = _resolve_run_dir(
        run_id
    )

    trajectory_path = (
        run_dir
        / "trajectory_communication.csv"
    )

    if not trajectory_path.is_file():
        raise FileNotFoundError(
            trajectory_path
        )

    def to_float(value):
        if value is None:
            return None

        value = str(value).strip()

        if value == "":
            return None

        try:
            return float(value)
        except ValueError:
            return None

    def to_bool(value):
        if value is None:
            return None

        value = str(value).strip().lower()

        if value == "true":
            return True

        if value == "false":
            return False

        return None

    points = []

    with trajectory_path.open(
        "r",
        encoding="utf-8",
        newline="",
    ) as csv_file:
        reader = csv.DictReader(
            csv_file
        )

        for row in reader:
            points.append(
                {
                    "elapsed_s": to_float(
                        row.get("elapsed_s")
                    ),
                    "east_m": to_float(
                        row.get("east_m")
                    ),
                    "north_m": to_float(
                        row.get("north_m")
                    ),
                    "altitude_m": to_float(
                        row.get("altitude_m")
                    ),
                    "in_air": to_bool(
                        row.get("in_air")
                    ),
                    "serving_bs": row.get(
                        "serving_bs"
                    ),
                    "distance_m": to_float(
                        row.get("distance_m")
                    ),
                    "path_loss_db": to_float(
                        row.get("path_loss_db")
                    ),
                    "rsrp_dbm": to_float(
                        row.get("rsrp_dbm")
                    ),
                    "sinr_db": to_float(
                        row.get("sinr_db")
                    ),
                    "coverage_score": to_float(
                        row.get("coverage_score")
                    ),
                    "coverage_level": row.get(
                        "coverage_level"
                    ),
                }
            )

    sampled_points = points[
        ::stride
    ]

    return {
        "run_id": run_id,
        "source_artifact": (
            "trajectory_communication.csv"
        ),
        "total_points": len(
            points
        ),
        "returned_points": len(
            sampled_points
        ),
        "stride": stride,
        "points": sampled_points,
    }


def get_run_incidents(
    run_id: str,
) -> dict:
    """
    Return normalized communication degradation,
    replan, recovery, and Advisor episodes for
    one persisted run.
    """

    run_dir = _resolve_run_dir(
        run_id
    )

    artifact_path = (
        run_dir
        / "multi_replan_evaluation.json"
    )

    if not artifact_path.is_file():
        raise FileNotFoundError(
            artifact_path
        )

    document = _read_json_if_exists(
        artifact_path
    )

    if not isinstance(
        document,
        dict,
    ):
        raise ValueError(
            "Invalid multi_replan_evaluation.json"
        )

    raw_episodes = (
        document.get(
            "episodes",
            [],
        )
        or []
    )

    episodes = []

    for raw_episode in raw_episodes:
        if not isinstance(
            raw_episode,
            dict,
        ):
            continue

        degradation = (
            raw_episode.get(
                "degradation"
            )
            or {}
        )

        fast_policy = (
            raw_episode.get(
                "fast_policy"
            )
            or {}
        )

        route_application = (
            raw_episode.get(
                "route_application"
            )
            or {}
        )

        recovery = (
            raw_episode.get(
                "recovery"
            )
            or {}
        )

        communication_change = (
            raw_episode.get(
                "communication_change"
            )
            or {}
        )

        advisor = (
            raw_episode.get(
                "advisor"
            )
            or {}
        )

        advisor_result = (
            advisor.get(
                "result"
            )
            or {}
        )

        decision_latency_s = (
            fast_policy.get(
                "total_latency_s"
            )
        )

        decision_latency_ms = None

        if isinstance(
            decision_latency_s,
            (int, float),
        ):
            decision_latency_ms = (
                decision_latency_s
                * 1000.0
            )

        episodes.append(
            {
                "episode_index": (
                    raw_episode.get(
                        "episode_index"
                    )
                ),
                "incident": {
                    "timestamp_utc": (
                        degradation.get(
                            "timestamp_utc"
                        )
                    ),
                    "elapsed_s": (
                        degradation.get(
                            "elapsed_s"
                        )
                    ),
                    "east_m": (
                        degradation.get(
                            "east_m"
                        )
                    ),
                    "north_m": (
                        degradation.get(
                            "north_m"
                        )
                    ),
                    "rsrp_dbm": (
                        degradation.get(
                            "rsrp_dbm"
                        )
                    ),
                    "sinr_db": (
                        degradation.get(
                            "sinr_db"
                        )
                    ),
                    "coverage_score": (
                        degradation.get(
                            "coverage_score"
                        )
                    ),
                },
                "decision": {
                    "decision": (
                        fast_policy.get(
                            "decision"
                        )
                    ),
                    "selected_planner": (
                        fast_policy.get(
                            "selected_planner"
                        )
                    ),
                    "reason": (
                        fast_policy.get(
                            "reason"
                        )
                    ),
                    "triggered_rules": (
                        fast_policy.get(
                            "triggered_rules",
                            [],
                        )
                        or []
                    ),
                    "decision_source": (
                        fast_policy.get(
                            "decision_source"
                        )
                    ),
                    "latency_s": (
                        decision_latency_s
                    ),
                    "latency_ms": (
                        decision_latency_ms
                    ),
                },
                "route_application": {
                    "timestamp_utc": (
                        route_application.get(
                            "timestamp_utc"
                        )
                    ),
                    "incident_to_route_apply_s": (
                        route_application.get(
                            "incident_to_route_apply_s"
                        )
                    ),
                    "east_m": (
                        route_application.get(
                            "east_m"
                        )
                    ),
                    "north_m": (
                        route_application.get(
                            "north_m"
                        )
                    ),
                    "replan_index": (
                        route_application.get(
                            "replan_index"
                        )
                    ),
                    "waypoint_count": (
                        route_application.get(
                            "waypoint_count"
                        )
                    ),
                },
                "recovery": {
                    "timestamp_utc": (
                        recovery.get(
                            "timestamp_utc"
                        )
                    ),
                    "elapsed_s": (
                        recovery.get(
                            "elapsed_s"
                        )
                    ),
                    "east_m": (
                        recovery.get(
                            "east_m"
                        )
                    ),
                    "north_m": (
                        recovery.get(
                            "north_m"
                        )
                    ),
                    "recovery_time_s": (
                        recovery.get(
                            "incident_to_recovery_s"
                        )
                    ),
                    "recovery_path_m": (
                        recovery.get(
                            "incident_to_recovery_path_m"
                        )
                    ),
                },
                "communication_change": {
                    "incident_rsrp_dbm": (
                        communication_change.get(
                            "incident_rsrp_dbm"
                        )
                    ),
                    "recovery_rsrp_dbm": (
                        communication_change.get(
                            "recovery_rsrp_dbm"
                        )
                    ),
                    "rsrp_improvement_db": (
                        communication_change.get(
                            "rsrp_improvement_db"
                        )
                    ),
                    "incident_sinr_db": (
                        communication_change.get(
                            "incident_sinr_db"
                        )
                    ),
                    "recovery_sinr_db": (
                        communication_change.get(
                            "recovery_sinr_db"
                        )
                    ),
                    "sinr_improvement_db": (
                        communication_change.get(
                            "sinr_improvement_db"
                        )
                    ),
                    "incident_coverage_score": (
                        communication_change.get(
                            "incident_coverage_score"
                        )
                    ),
                    "recovery_coverage_score": (
                        communication_change.get(
                            "recovery_coverage_score"
                        )
                    ),
                    "coverage_score_improvement": (
                        communication_change.get(
                            "coverage_score_improvement"
                        )
                    ),
                },
                "advisor": {
                    "status": (
                        advisor.get(
                            "status"
                        )
                    ),
                    "latency_s": (
                        advisor.get(
                            "latency_s"
                        )
                    ),
                    "result_status": (
                        advisor_result.get(
                            "status"
                        )
                    ),
                    "error_type": (
                        advisor_result.get(
                            "error_type"
                        )
                    ),
                    "error": (
                        advisor_result.get(
                            "error"
                        )
                    ),
                },
            }
        )

    return {
        "run_id": run_id,
        "source_artifact": (
            "multi_replan_evaluation.json"
        ),
        "mission_status": (
            document.get(
                "mission_status"
            )
        ),
        "evaluation_mode": (
            document.get(
                "evaluation_mode"
            )
        ),
        "episode_count": len(
            episodes
        ),
        "episodes": episodes,
        "overall": (
            document.get(
                "overall",
                {},
            )
            or {}
        ),
    }


def get_run_artifact_path(
    run_id: str,
    artifact_name: str,
) -> Path:
    """
    Resolve one artifact file belonging directly
    to a persisted run directory.

    The artifact must be a direct child of the
    run directory. Path traversal is rejected.
    """

    if (
        not artifact_name
        or "/" in artifact_name
        or "\\" in artifact_name
        or artifact_name in {".", ".."}
    ):
        raise FileNotFoundError(
            artifact_name
        )

    run_dir = _resolve_run_dir(
        run_id
    )

    artifact_path = (
        run_dir
        / artifact_name
    ).resolve()

    resolved_run_dir = (
        run_dir.resolve()
    )

    if artifact_path.parent != resolved_run_dir:
        raise FileNotFoundError(
            artifact_name
        )

    if not artifact_path.is_file():
        raise FileNotFoundError(
            artifact_name
        )

    return artifact_path
