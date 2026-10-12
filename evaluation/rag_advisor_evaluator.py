import json

from collections import Counter
from pathlib import Path


def _load_json(
    path: Path,
) -> dict:
    return json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )


def _safe_float(
    value,
):
    try:
        if value is None:
            return None

        return float(value)

    except (
        TypeError,
        ValueError,
    ):
        return None


def _mean(
    values: list[float],
):
    if not values:
        return None

    return (
        sum(values)
        / len(values)
    )


def _latency_summary(
    values: list[float],
) -> dict:
    if not values:
        return {
            "count": 0,
            "mean_s": None,
            "min_s": None,
            "max_s": None,
        }

    return {
        "count":
            len(values),

        "mean_s":
            _mean(values),

        "min_s":
            min(values),

        "max_s":
            max(values),
    }


def _ratio(
    numerator: int,
    denominator: int,
):
    if denominator <= 0:
        return None

    return (
        numerator
        / denominator
    )


def evaluate_rag_advisor(
    run_dir,
) -> dict:
    """
    Evaluate persisted Incident Advisor and
    RAG records for one mission run.

    This evaluator is post-flight only.
    It has no flight-control authority.
    """

    run_dir = Path(
        run_dir
    )

    incident_path = (
        run_dir
        / "incident_events.json"
    )

    if not incident_path.exists():
        raise FileNotFoundError(
            incident_path
        )

    document = _load_json(
        incident_path
    )

    mission_id = document.get(
        "mission_id"
    )

    incident_records = (
        document.get(
            "incident_records",
            [],
        )
    )

    advisor_records = [
        record
        for record in incident_records
        if (
            record.get("event_type")
            == "INCIDENT_ADVISORY"
        )
    ]


    # ==================================================
    # Advisor status
    # ==================================================
    completed_count = 0
    failed_count = 0

    rag_enabled_count = 0
    rag_used_count = 0
    rag_failure_count = 0

    advisor_latencies = []
    background_latencies = []
    rag_latencies = []

    confidences = []

    severity_counter = Counter()

    chunk_counter = Counter()
    source_counter = Counter()
    section_counter = Counter()


    # ==================================================
    # Safety / authority consistency
    # ==================================================
    fast_decision_comparable = 0
    fast_decision_matches = 0

    planner_comparable = 0
    planner_matches = 0


    # ==================================================
    # Per-advisor summaries
    # ==================================================
    advisor_summaries = []


    for index, record in enumerate(
        advisor_records,
        start=1,
    ):
        result = (
            record.get(
                "result",
                {},
            )
            or {}
        )

        status = result.get(
            "status"
        )

        if status == "COMPLETED":
            completed_count += 1

        elif status == "FAILED":
            failed_count += 1


        # ----------------------------------------------
        # RAG usage
        # ----------------------------------------------
        rag_enabled = bool(
            result.get(
                "rag_enabled",
                False,
            )
        )

        rag_used = bool(
            result.get(
                "rag_used",
                False,
            )
        )

        if rag_enabled:
            rag_enabled_count += 1

        if rag_used:
            rag_used_count += 1

        if (
            result.get(
                "rag_error_type"
            )
            is not None
            or result.get(
                "rag_error"
            )
            is not None
        ):
            rag_failure_count += 1


        # ----------------------------------------------
        # Latencies
        # ----------------------------------------------
        advisor_latency = (
            _safe_float(
                result.get(
                    "latency_s"
                )
            )
        )

        if advisor_latency is not None:
            advisor_latencies.append(
                advisor_latency
            )


        background_latency = (
            _safe_float(
                record.get(
                    "background_latency_s"
                )
            )
        )

        if (
            background_latency
            is not None
        ):
            background_latencies.append(
                background_latency
            )


        rag_latency = (
            _safe_float(
                result.get(
                    "rag_retrieval_latency_s"
                )
            )
        )

        if rag_latency is not None:
            rag_latencies.append(
                rag_latency
            )


        # ----------------------------------------------
        # Advisory quality metadata
        # ----------------------------------------------
        advisory = (
            result.get(
                "advisory",
                {},
            )
            or {}
        )

        severity = advisory.get(
            "severity"
        )

        if severity:
            severity_counter[
                severity
            ] += 1


        confidence = (
            _safe_float(
                advisory.get(
                    "confidence"
                )
            )
        )

        if confidence is not None:
            confidences.append(
                confidence
            )


        # ----------------------------------------------
        # Retrieval traceability
        # ----------------------------------------------
        chunk_ids = (
            result.get(
                "rag_chunk_ids",
                [],
            )
            or []
        )

        sources = (
            result.get(
                "rag_sources",
                [],
            )
            or []
        )

        sections = (
            result.get(
                "rag_sections",
                [],
            )
            or []
        )

        chunk_counter.update(
            chunk_ids
        )

        source_counter.update(
            sources
        )

        section_counter.update(
            sections
        )


        # ----------------------------------------------
        # Safety consistency:
        #
        # Advisor should observe the already-made
        # deterministic decision, not replace it.
        # ----------------------------------------------
        fast_decision = record.get(
            "fast_decision"
        )

        observed_fast_decision = (
            result.get(
                "observed_fast_decision"
            )
        )

        if (
            fast_decision is not None
            and observed_fast_decision
            is not None
        ):
            fast_decision_comparable += 1

            if (
                fast_decision
                == observed_fast_decision
            ):
                fast_decision_matches += 1


        selected_planner = record.get(
            "selected_planner"
        )

        observed_planner = (
            result.get(
                "observed_selected_planner"
            )
        )

        if (
            selected_planner is not None
            and observed_planner is not None
        ):
            planner_comparable += 1

            if (
                selected_planner
                == observed_planner
            ):
                planner_matches += 1


        advisor_summaries.append(
            {
                "index":
                    index,

                "action":
                    record.get(
                        "action"
                    ),

                "status":
                    status,

                "fast_decision":
                    fast_decision,

                "selected_planner":
                    selected_planner,

                "rag_enabled":
                    rag_enabled,

                "rag_used":
                    rag_used,

                "rag_chunk_ids":
                    list(
                        chunk_ids
                    ),

                "rag_retrieval_latency_s":
                    rag_latency,

                "advisor_latency_s":
                    advisor_latency,

                "background_latency_s":
                    background_latency,

                "severity":
                    severity,

                "confidence":
                    confidence,

                "error_type":
                    result.get(
                        "error_type"
                    ),
            }
        )


    advisor_count = len(
        advisor_records
    )


    report = {
        "mission_id":
            mission_id,

        "advisor_record_count":
            advisor_count,

        "advisor_completed_count":
            completed_count,

        "advisor_failed_count":
            failed_count,

        "advisor_success_rate":
            _ratio(
                completed_count,
                advisor_count,
            ),

        "rag": {
            "enabled_count":
                rag_enabled_count,

            "used_count":
                rag_used_count,

            "usage_rate":
                _ratio(
                    rag_used_count,
                    rag_enabled_count,
                ),

            "failure_count":
                rag_failure_count,

            "retrieval_latency":
                _latency_summary(
                    rag_latencies
                ),
        },

        "advisor_latency":
            _latency_summary(
                advisor_latencies
            ),

        "background_latency":
            _latency_summary(
                background_latencies
            ),

        "advisory_quality": {
            "confidence_count":
                len(confidences),

            "mean_confidence":
                _mean(
                    confidences
                ),

            "min_confidence":
                (
                    min(confidences)
                    if confidences
                    else None
                ),

            "max_confidence":
                (
                    max(confidences)
                    if confidences
                    else None
                ),

            "severity_counts":
                dict(
                    sorted(
                        severity_counter.items()
                    )
                ),
        },

        "retrieval_traceability": {
            "unique_chunk_count":
                len(
                    chunk_counter
                ),

            "unique_chunk_ids":
                sorted(
                    chunk_counter
                ),

            "chunk_hit_counts":
                dict(
                    sorted(
                        chunk_counter.items()
                    )
                ),

            "source_counts":
                dict(
                    sorted(
                        source_counter.items()
                    )
                ),

            "section_counts":
                dict(
                    sorted(
                        section_counter.items()
                    )
                ),
        },

        "safety_consistency": {
            "fast_decision_comparable":
                fast_decision_comparable,

            "fast_decision_matches":
                fast_decision_matches,

            "fast_decision_match_rate":
                _ratio(
                    fast_decision_matches,
                    fast_decision_comparable,
                ),

            "selected_planner_comparable":
                planner_comparable,

            "selected_planner_matches":
                planner_matches,

            "selected_planner_match_rate":
                _ratio(
                    planner_matches,
                    planner_comparable,
                ),
        },

        "advisor_records":
            advisor_summaries,
    }

    return report


def evaluate_rag_advisor_if_available(
    run_dir,
):
    """
    Evaluate and persist RAG / Advisor metrics
    only when persisted Advisor records exist.

    Returns:
        report dict, or None when no evaluation
        is applicable.
    """

    run_dir = Path(
        run_dir
    )

    incident_path = (
        run_dir
        / "incident_events.json"
    )

    if not incident_path.exists():
        return None

    document = _load_json(
        incident_path
    )

    records = (
        document.get(
            "incident_records",
            [],
        )
    )

    has_advisor = any(
        record.get(
            "event_type"
        )
        == "INCIDENT_ADVISORY"
        for record in records
    )

    if not has_advisor:
        return None


    report = (
        evaluate_rag_advisor(
            run_dir
        )
    )

    output_path = (
        run_dir
        / "rag_advisor_evaluation.json"
    )

    output_path.write_text(
        json.dumps(
            report,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    return report
