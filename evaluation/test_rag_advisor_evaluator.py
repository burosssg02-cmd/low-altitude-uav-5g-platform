import json

from evaluation.rag_advisor_evaluator import (
    evaluate_rag_advisor,
    evaluate_rag_advisor_if_available,
)


def write_incident_file(
    tmp_path,
    records,
):
    path = (
        tmp_path
        / "incident_events.json"
    )

    path.write_text(
        json.dumps(
            {
                "mission_id":
                    "mission_rag_eval_test",

                "incident_records":
                    records,
            }
        ),
        encoding="utf-8",
    )


def completed_record():
    return {
        "event_type":
            "INCIDENT_ADVISORY",

        "action":
            "ADVISOR_COMPLETED",

        "mission_id":
            "mission_rag_eval_test",

        "fast_decision":
            "REPLAN_RECOMMENDED",

        "selected_planner":
            "communication_aware",

        "background_latency_s":
            9.8,

        "result": {
            "status":
                "COMPLETED",

            "observed_fast_decision":
                "REPLAN_RECOMMENDED",

            "observed_selected_planner":
                "communication_aware",

            "latency_s":
                9.6,

            "rag_enabled":
                True,

            "rag_used":
                True,

            "rag_retrieval_latency_s":
                0.31,

            "rag_chunk_ids": [
                "communication:0001",
                "communication:0005",
            ],

            "rag_sources": [
                "communication_incidents.md",
                "communication_incidents.md",
            ],

            "rag_sections": [
                "Communication degradation",
                "Fast Incident Policy",
            ],

            "advisory": {
                "severity":
                    "WARNING",

                "diagnosis":
                    "Weak coverage.",

                "decision_explanation":
                    "Replan was justified.",

                "recommended_followup":
                    "Review after flight.",

                "confidence":
                    0.95,
            },
        },
    }


def test_completed_rag_advisor_metrics(
    tmp_path,
):
    write_incident_file(
        tmp_path,
        [
            completed_record()
        ],
    )

    report = evaluate_rag_advisor(
        tmp_path
    )

    assert (
        report[
            "advisor_record_count"
        ]
        == 1
    )

    assert (
        report[
            "advisor_completed_count"
        ]
        == 1
    )

    assert (
        report[
            "advisor_success_rate"
        ]
        == 1.0
    )

    assert (
        report["rag"]["used_count"]
        == 1
    )

    assert (
        report["rag"]["usage_rate"]
        == 1.0
    )

    assert (
        report[
            "advisory_quality"
        ][
            "mean_confidence"
        ]
        == 0.95
    )


def test_retrieval_traceability(
    tmp_path,
):
    write_incident_file(
        tmp_path,
        [
            completed_record()
        ],
    )

    report = evaluate_rag_advisor(
        tmp_path
    )

    trace = report[
        "retrieval_traceability"
    ]

    assert (
        trace["unique_chunk_count"]
        == 2
    )

    assert (
        trace[
            "chunk_hit_counts"
        ][
            "communication:0001"
        ]
        == 1
    )

    assert (
        trace[
            "source_counts"
        ][
            "communication_incidents.md"
        ]
        == 2
    )


def test_safety_consistency(
    tmp_path,
):
    write_incident_file(
        tmp_path,
        [
            completed_record()
        ],
    )

    report = evaluate_rag_advisor(
        tmp_path
    )

    safety = report[
        "safety_consistency"
    ]

    assert (
        safety[
            "fast_decision_match_rate"
        ]
        == 1.0
    )

    assert (
        safety[
            "selected_planner_match_rate"
        ]
        == 1.0
    )


def test_rag_failure_is_counted(
    tmp_path,
):
    record = completed_record()

    record["result"][
        "rag_used"
    ] = False

    record["result"][
        "rag_error_type"
    ] = "RuntimeError"

    record["result"][
        "rag_error"
    ] = "retrieval failed"

    write_incident_file(
        tmp_path,
        [record],
    )

    report = evaluate_rag_advisor(
        tmp_path
    )

    assert (
        report["rag"][
            "failure_count"
        ]
        == 1
    )

    assert (
        report["rag"][
            "used_count"
        ]
        == 0
    )


def test_if_available_writes_file(
    tmp_path,
):
    write_incident_file(
        tmp_path,
        [
            completed_record()
        ],
    )

    report = (
        evaluate_rag_advisor_if_available(
            tmp_path
        )
    )

    assert report is not None

    output_path = (
        tmp_path
        / "rag_advisor_evaluation.json"
    )

    assert output_path.exists()

    saved = json.loads(
        output_path.read_text(
            encoding="utf-8"
        )
    )

    assert (
        saved[
            "advisor_completed_count"
        ]
        == 1
    )


def test_if_available_skips_without_advisor(
    tmp_path,
):
    write_incident_file(
        tmp_path,
        [
            {
                "event_type":
                    "COMMUNICATION_DEGRADED"
            }
        ],
    )

    result = (
        evaluate_rag_advisor_if_available(
            tmp_path
        )
    )

    assert result is None

    assert not (
        tmp_path
        / "rag_advisor_evaluation.json"
    ).exists()
