import json
from types import SimpleNamespace

from agent.incident_context import (
    build_incident_context,
)

from agent.realtime_incident_agent import (
    run_realtime_incident_agent,
)


def make_context(
    planner="normal",
):
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

        planner=planner,

        altitude_m=5.0,

        communication_weight=2.0,
    )


COMPARISON = {
    "normal": {
        "planner":
            "normal",

        "planned_distance_m":
            30.0,

        "mean_coverage_score":
            0.515,

        "min_coverage_score":
            0.454,

        "mean_rsrp_dbm":
            -95.44,

        "min_rsrp_dbm":
            -98.60,

        "mean_sinr_db":
            1.09,

        "min_sinr_db":
            -0.01,

        "handover_count":
            2,
    },

    "communication_aware": {
        "planner":
            "communication_aware",

        "planned_distance_m":
            30.0,

        "mean_coverage_score":
            0.675,

        "min_coverage_score":
            0.502,

        "mean_rsrp_dbm":
            -86.29,

        "min_rsrp_dbm":
            -97.65,

        "mean_sinr_db":
            3.76,

        "min_sinr_db":
            1.63,

        "handover_count":
            0,
    },
}


class FakeCompletions:
    def __init__(
        self,
        arguments,
    ):
        self.arguments = arguments
        self.call_count = 0

    def create(
        self,
        **kwargs,
    ):
        self.call_count += 1

        tool_call = (
            SimpleNamespace(
                function=(
                    SimpleNamespace(
                        arguments=json.dumps(
                            self.arguments
                        )
                    )
                )
            )
        )

        message = (
            SimpleNamespace(
                tool_calls=[
                    tool_call
                ]
            )
        )

        choice = (
            SimpleNamespace(
                message=message
            )
        )

        return SimpleNamespace(
            choices=[
                choice
            ]
        )


class FakeClient:
    def __init__(
        self,
        arguments,
    ):
        self.completions = (
            FakeCompletions(
                arguments
            )
        )

        self.chat = (
            SimpleNamespace(
                completions=(
                    self.completions
                )
            )
        )


def test_realtime_agent_uses_one_llm_call():
    context = make_context()

    compare_calls = []

    def fake_compare(
        received_context,
    ):
        compare_calls.append(
            received_context
        )

        return COMPARISON

    client = FakeClient(
        {
            "decision":
                "REPLAN_RECOMMENDED",

            "selected_planner":
                "communication_aware",

            "reason":
                "Communication is better.",
        }
    )

    result = (
        run_realtime_incident_agent(
            context,

            client=client,

            model="fake-model",

            compare_runner=(
                fake_compare
            ),
        )
    )

    assert len(compare_calls) == 1

    assert (
        client.completions.call_count
        == 1
    )

    assert (
        result["decision"]["decision"]
        == "REPLAN_RECOMMENDED"
    )

    assert (
        result["fallback_used"]
        is False
    )


def test_metrics_are_not_taken_from_llm():
    context = make_context()

    client = FakeClient(
        {
            "decision":
                "REPLAN_RECOMMENDED",

            "selected_planner":
                "communication_aware",

            "reason":
                "Use communication route.",

            # Any extra invented metrics
            # are ignored by our code.
            "mean_rsrp_dbm":
                999.0,
        }
    )

    result = (
        run_realtime_incident_agent(
            context,

            client=client,

            model="fake-model",

            compare_runner=(
                lambda context:
                    COMPARISON
            ),
        )
    )

    assert (
        result["decision"]
        ["communication_aware"]
        ["mean_rsrp_dbm"]
        == -86.29
    )


def test_invalid_llm_decision_falls_back():
    context = make_context(
        planner="normal"
    )

    client = FakeClient(
        {
            "decision":
                "REPLAN_RECOMMENDED",

            # Invalid combination.
            "selected_planner":
                "normal",

            "reason":
                "invalid",
        }
    )

    result = (
        run_realtime_incident_agent(
            context,

            client=client,

            model="fake-model",

            compare_runner=(
                lambda context:
                    COMPARISON
            ),
        )
    )

    assert (
        result["fallback_used"]
        is True
    )

    assert (
        result["decision"]["decision"]
        == "KEEP_ROUTE"
    )

    assert (
        result["decision"]
        ["selected_planner"]
        == "normal"
    )
