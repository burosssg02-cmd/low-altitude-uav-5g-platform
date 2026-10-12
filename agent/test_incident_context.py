import pytest

from agent.incident_context import (
    build_incident_context,
)


def test_build_real_flight_incident_context():
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

    context = build_incident_context(
        event=event,

        mission_id="mission_test",

        mission_start=(1, 3),
        mission_goal=(8, 3),

        planner="normal",

        altitude_m=5.0,

        communication_weight=2.0,
    )

    assert (
        context.incident_type
        == "COMMUNICATION_DEGRADED"
    )

    assert (
        context.current_grid
        == (5, 0)
    )

    assert (
        context.mission_goal
        == (8, 3)
    )

    assert (
        context.planner
        == "normal"
    )

    assert (
        context.rsrp_dbm
        == pytest.approx(-97.9)
    )

    assert (
        context.coverage_score
        == pytest.approx(0.491)
    )


def test_context_serialization():
    event = {
        "event_type":
            "COMMUNICATION_DEGRADED",

        "east_m": 25.0,
        "north_m": 15.0,
        "altitude_m": 5.0,

        "rsrp_dbm": -98.1,
        "sinr_db": 1.2,
        "coverage_score": 0.477,

        "serving_bs": "BS1",

        "reasons": [
            "LOW_RSRP",
            "LOW_COVERAGE_SCORE",
        ],
    }

    context = build_incident_context(
        event=event,
        mission_id="mission_test",
        mission_start=(1, 3),
        mission_goal=(8, 3),
        planner="normal",
        altitude_m=5.0,
    )

    data = context.to_dict()

    assert (
        data["current_grid"]
        == (6, 0)
    )

    assert (
        data["mission_goal"]
        == (8, 3)
    )

    assert (
        data["incident_type"]
        == "COMMUNICATION_DEGRADED"
    )


def test_missing_required_field_fails():
    event = {
        "event_type":
            "COMMUNICATION_DEGRADED",

        "east_m": 22.4,
        "north_m": 14.9,

        # rsrp_dbm deliberately missing
        "sinr_db": 1.9,
        "coverage_score": 0.491,
    }

    with pytest.raises(
        ValueError,
        match="missing fields",
    ):
        build_incident_context(
            event=event,
            mission_id="mission_test",
            mission_start=(1, 3),
            mission_goal=(8, 3),
            planner="normal",
            altitude_m=5.0,
        )
