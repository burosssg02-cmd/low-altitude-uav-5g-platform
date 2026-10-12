from unittest.mock import patch

from agent.incident_context import (
    build_incident_context,
)
from agent.incident_tools import (
    compare_incident_routes,
)


def test_incident_route_compare_arguments():
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

    fake_result = {
        "normal": {},
        "communication_aware": {},
    }

    with patch(
        "agent.incident_tools."
        "route_compare_api_tool",
        return_value=fake_result,
    ) as tool:
        result = compare_incident_routes(
            context
        )

    assert result == fake_result

    tool.assert_called_once_with(
        start=[5, 0],
        goal=[8, 3],
        altitude_m=5.0,
        communication_weight=2.0,
        radio_origin=[1, 3],
    )
