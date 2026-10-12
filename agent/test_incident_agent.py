import pytest

from agent.incident_agent import (
    build_incident_decision,
)
from agent.incident_context import (
    build_incident_context,
)


def make_context():
    event = {
        "event_type":
            "COMMUNICATION_DEGRADED",
        "east_m": 22.4,
        "north_m": 14.9,
        "altitude_m": 5.0,
        "rsrp_dbm": -97.9,
        "sinr_db": 1.9,
        "coverage_score": 0.491,
        "serving_bs": "BS1",
        "reasons": [
            "LOW_RSRP",
            "LOW_COVERAGE_SCORE",
        ],
    }

    return build_incident_context(
        event=event,
        mission_id="mission_test",
        mission_start=(1, 3),
        mission_goal=(8, 3),
        planner="normal",
        altitude_m=5.0,
        communication_weight=2.0,
    )


def make_comparison():
    return {
        "normal": {
            "planner": "normal",
            "planned_distance_m": 30.0,
            "mean_coverage_score": 0.515,
            "min_coverage_score": 0.454,
            "mean_rsrp_dbm": -95.44,
            "min_rsrp_dbm": -98.60,
            "mean_sinr_db": 1.09,
            "min_sinr_db": -0.01,
            "handover_count": 2,
        },
        "communication_aware": {
            "planner":
                "communication_aware",
            "planned_distance_m": 30.0,
            "mean_coverage_score": 0.675,
            "min_coverage_score": 0.502,
            "mean_rsrp_dbm": -86.29,
            "min_rsrp_dbm": -97.65,
            "mean_sinr_db": 3.76,
            "min_sinr_db": 1.63,
            "handover_count": 0,
        },
    }


def test_replan_decision_builds():
    result = build_incident_decision(
        context=make_context(),
        comparison=make_comparison(),
        decision_arguments={
            "decision":
                "REPLAN_RECOMMENDED",
            "selected_planner":
                "communication_aware",
            "reason":
                "Communication metrics improve.",
        },
    )

    assert (
        result.decision
        == "REPLAN_RECOMMENDED"
    )

    assert (
        result.communication_aware
        .planned_distance_m
        == 30.0
    )

    assert (
        result.communication_aware
        .handover_count
        == 0
    )


def test_invalid_replan_planner_fails():
    with pytest.raises(
        ValueError,
        match="communication_aware",
    ):
        build_incident_decision(
            context=make_context(),
            comparison=make_comparison(),
            decision_arguments={
                "decision":
                    "REPLAN_RECOMMENDED",
                "selected_planner":
                    "normal",
                "reason":
                    "Invalid combination.",
            },
        )


def test_invalid_keep_route_planner_fails():
    with pytest.raises(
        ValueError,
        match="preserve",
    ):
        build_incident_decision(
            context=make_context(),
            comparison=make_comparison(),
            decision_arguments={
                "decision":
                    "KEEP_ROUTE",
                "selected_planner":
                    "communication_aware",
                "reason":
                    "Invalid combination.",
            },
        )
