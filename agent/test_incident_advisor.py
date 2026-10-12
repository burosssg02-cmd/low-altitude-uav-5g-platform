import json
from types import SimpleNamespace

from agent.incident_advisor import (
    run_incident_advisor,
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

        mission_id="mission_advisor_test",

        mission_start=(1, 3),
        mission_goal=(8, 3),

        planner="normal",

        altitude_m=5.0,

        communication_weight=2.0,
    )


FAST_DECISION = {
    "decision":
        "REPLAN_RECOMMENDED",

    "selected_planner":
        "communication_aware",

    "reason":
        "Communication improvement is sufficient.",

    "triggered_rules": [
        "MEAN_SCORE_IMPROVED",
        "MEAN_RSRP_IMPROVED",
        "MEAN_SINR_IMPROVED",
        "FEWER_HANDOVERS",
    ],

    "metrics": {
        "mean_rsrp_gain_db":
            9.15,

        "mean_sinr_gain_db":
            2.67,
    },
}


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
        arguments=None,
        error=None,
    ):
        self.arguments = arguments
        self.error = error
        self.call_count = 0
        self.last_kwargs = None

    def create(
        self,
        **kwargs,
    ):
        self.call_count += 1
        self.last_kwargs = kwargs

        if self.error is not None:
            raise self.error

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

        return SimpleNamespace(
            choices=[
                SimpleNamespace(
                    message=message
                )
            ]
        )


class FakeClient:
    def __init__(
        self,
        *,
        arguments=None,
        error=None,
    ):
        self.completions = (
            FakeCompletions(
                arguments=arguments,
                error=error,
            )
        )

        self.chat = (
            SimpleNamespace(
                completions=(
                    self.completions
                )
            )
        )


def test_advisor_success():
    client = FakeClient(
        arguments={
            "severity":
                "WARNING",

            "diagnosis":
                "Weak coverage detected.",

            "decision_explanation":
                "Communication-aware route "
                "improves communication metrics.",

            "recommended_followup":
                "Record the incident for "
                "post-flight evaluation.",

            "confidence":
                0.92,
        }
    )

    result = run_incident_advisor(
        make_context(),
        FAST_DECISION,
        COMPARISON,

        client=client,
        model="fake-model",
        enable_rag=False,
    )

    assert (
        client.completions.call_count
        == 1
    )

    assert (
        client.completions
        .last_kwargs[
            "max_completion_tokens"
        ]
        == 768
    )

    assert (
        result["status"]
        == "COMPLETED"
    )

    assert (
        result[
            "observed_fast_decision"
        ]
        == "REPLAN_RECOMMENDED"
    )

    assert (
        result["advisory"]
        ["severity"]
        == "WARNING"
    )


def test_advisor_failure_does_not_raise():
    client = FakeClient(
        error=RuntimeError(
            "simulated API failure"
        )
    )

    result = run_incident_advisor(
        make_context(),
        FAST_DECISION,
        COMPARISON,

        client=client,
        model="fake-model",
        enable_rag=False,
    )

    assert (
        result["status"]
        == "FAILED"
    )

    assert (
        result["error_type"]
        == "RuntimeError"
    )

    assert (
        result[
            "observed_fast_decision"
        ]
        == "REPLAN_RECOMMENDED"
    )



class FakeRAGRetriever:
    def search(
        self,
        query,
        *,
        top_k=5,
    ):
        from rag.document_loader import (
            KnowledgeChunk,
        )

        query_lower = (
            query.lower()
        )

        if "rsrp" in query_lower:
            chunk = KnowledgeChunk(
                chunk_id="radio:0001",
                source="radio.md",
                section="Communication degradation",
                content=(
                    "Low RSRP indicates weak "
                    "received signal strength."
                ),
            )

        elif (
            "fast incident policy"
            in query_lower
        ):
            chunk = KnowledgeChunk(
                chunk_id="policy:0001",
                source="policy.md",
                section="Fast Incident Policy",
                content=(
                    "The Fast Incident Policy is "
                    "deterministic and does not "
                    "use an LLM."
                ),
            )

        else:
            chunk = KnowledgeChunk(
                chunk_id="advisor:0001",
                source="advisor.md",
                section="LLM Incident Advisor",
                content=(
                    "The Advisor has no authority "
                    "to directly control PX4 or "
                    "override the deterministic "
                    "flight decision."
                ),
            )

        return [
            SimpleNamespace(
                chunk=chunk
            )
        ][:top_k]


class FailingRAGRetriever:
    def search(
        self,
        query,
        *,
        top_k=5,
    ):
        raise RuntimeError(
            "simulated RAG failure"
        )


def make_success_client():
    return FakeClient(
        arguments={
            "severity":
                "WARNING",

            "diagnosis":
                "Weak coverage detected.",

            "decision_explanation":
                (
                    "The deterministic policy "
                    "selected the communication-"
                    "aware route."
                ),

            "recommended_followup":
                (
                    "Record the incident for "
                    "post-flight evaluation."
                ),

            "confidence":
                0.92,
        }
    )


def test_advisor_includes_rag_context():
    client = make_success_client()

    result = run_incident_advisor(
        make_context(),
        FAST_DECISION,
        COMPARISON,

        client=client,
        model="fake-model",

        enable_rag=True,
        rag_retriever=(
            FakeRAGRetriever()
        ),
    )

    assert (
        result["status"]
        == "COMPLETED"
    )

    assert (
        result["rag_used"]
        is True
    )

    assert (
        "radio:0001"
        in result["rag_chunk_ids"]
    )

    assert (
        "policy:0001"
        in result["rag_chunk_ids"]
    )

    assert (
        "advisor:0001"
        in result["rag_chunk_ids"]
    )

    messages = (
        client.completions
        .last_kwargs["messages"]
    )

    user_prompt = (
        messages[1]["content"]
    )

    assert (
        "retrieved_knowledge"
        in user_prompt
    )

    assert (
        "No flight-control authority"
        in user_prompt
    )

    assert (
        "Fast Incident Policy"
        in user_prompt
    )


def test_rag_failure_does_not_break_advisor():
    client = make_success_client()

    result = run_incident_advisor(
        make_context(),
        FAST_DECISION,
        COMPARISON,

        client=client,
        model="fake-model",

        enable_rag=True,
        rag_retriever=(
            FailingRAGRetriever()
        ),
    )

    assert (
        result["status"]
        == "COMPLETED"
    )

    assert (
        result["rag_used"]
        is False
    )

    assert (
        result["rag_error_type"]
        == "RuntimeError"
    )

    assert (
        "simulated RAG failure"
        in result["rag_error"]
    )

    assert (
        result[
            "observed_fast_decision"
        ]
        == "REPLAN_RECOMMENDED"
    )
