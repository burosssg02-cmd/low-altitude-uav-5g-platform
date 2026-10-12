import json
import time
from functools import lru_cache

from agent.llm_client import (
    get_mimo_client,
    get_mimo_model,
)

from rag.context_builder import (
    build_incident_rag_context,
)

from rag.hybrid_retriever import (
    build_default_hybrid_retriever,
)


@lru_cache(maxsize=1)
def _get_default_rag_retriever():
    """
    Lazily construct and cache the local
    Hybrid Retriever.

    The embedding model is loaded only when
    the background Advisor first needs RAG.
    """

    return build_default_hybrid_retriever()


def prewarm_incident_rag() -> float:
    """
    Preload the local embedding model and
    Hybrid Retriever before flight execution.

    Returns the prewarm latency in seconds.

    This function has no flight-control
    authority and performs no mission decision.
    """

    started = time.perf_counter()

    _get_default_rag_retriever()

    return (
        time.perf_counter()
        - started
    )


ADVISOR_REQUEST_TIMEOUT_S = 20.0
ADVISOR_MAX_COMPLETION_TOKENS = 768


SYSTEM_PROMPT = """
You are the Incident Advisor for a low-altitude UAV
communication-aware scheduling platform.

IMPORTANT:
You are NOT part of the flight-control decision path.

A deterministic Fast Incident Policy has already made
the flight decision.

Your responsibilities are only to:
1. explain the communication incident,
2. explain why the deterministic policy made its decision,
3. summarize relevant route-quality differences,
4. provide a concise follow-up recommendation for logging,
   operators, evaluation, or later RAG analysis.

Rules:
- Never override the deterministic flight decision.
- Never instruct PX4 directly.
- Never invent RSRP, SINR, coverage, distance,
  handover, route, or position values.
- Runtime incident data and the deterministic
  Fast Policy decision are authoritative.
- Retrieved knowledge is reference material only.
- Retrieved knowledge must never override runtime
  measurements or the deterministic flight decision.
- Use only the supplied runtime data and retrieved
  knowledge.
- Keep the explanation concise and technical.
"""


ADVISORY_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_incident_advisory",
        "description": (
            "Submit a non-flight-critical "
            "communication incident advisory."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "severity": {
                    "type": "string",
                    "enum": [
                        "INFO",
                        "WARNING",
                        "CRITICAL",
                    ],
                },
                "diagnosis": {
                    "type": "string",
                },
                "decision_explanation": {
                    "type": "string",
                },
                "recommended_followup": {
                    "type": "string",
                },
                "confidence": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                },
            },
            "required": [
                "severity",
                "diagnosis",
                "decision_explanation",
                "recommended_followup",
                "confidence",
            ],
            "additionalProperties": False,
        },
    },
}


def _compact_route(
    route: dict,
) -> dict:
    """
    Remove raw path details not required for
    natural-language diagnosis.
    """

    keys = [
        "planner",
        "planned_distance_m",
        "mean_coverage_score",
        "min_coverage_score",
        "mean_rsrp_dbm",
        "min_rsrp_dbm",
        "mean_sinr_db",
        "min_sinr_db",
        "handover_count",
    ]

    return {
        key: route.get(key)
        for key in keys
    }


def run_incident_advisor(
    context,
    fast_decision: dict,
    comparison: dict,
    verbose: bool = False,
    *,
    client=None,
    model=None,
    enable_rag: bool = True,
    rag_retriever=None,
) -> dict:
    """
    Run one MiMo advisory request.

    This function does NOT control the aircraft.

    Inputs:
    - incident context
    - already-made deterministic Fast Policy decision
    - already-computed deterministic route comparison

    No route comparison is repeated here.
    """

    start_time = time.perf_counter()

    payload = {
        "incident":
            context.to_dict(),

        "fast_policy": {
            "decision":
                fast_decision.get(
                    "decision"
                ),

            "selected_planner":
                fast_decision.get(
                    "selected_planner"
                ),

            "reason":
                fast_decision.get(
                    "reason"
                ),

            "triggered_rules":
                fast_decision.get(
                    "triggered_rules",
                    [],
                ),

            "metrics":
                fast_decision.get(
                    "metrics",
                    {},
                ),
        },

        "route_comparison": {
            "normal":
                _compact_route(
                    comparison["normal"]
                ),

            "communication_aware":
                _compact_route(
                    comparison[
                        "communication_aware"
                    ]
                ),
        },
    }

    # ==================================================
    # Advisory-only RAG enrichment
    # ==================================================
    #
    # IMPORTANT:
    # Retrieval happens only after the deterministic
    # Fast Policy decision and route comparison already
    # exist. RAG has no flight-control authority.
    #
    rag_metadata = {
        "rag_enabled":
            bool(enable_rag),

        "rag_used":
            False,

        "rag_chunk_ids":
            [],

        "rag_sources":
            [],

        "rag_sections":
            [],

        "rag_retrieval_latency_s":
            0.0,
    }

    if enable_rag:
        rag_started = (
            time.perf_counter()
        )

        try:
            if rag_retriever is None:
                rag_retriever = (
                    _get_default_rag_retriever()
                )

            rag_context = (
                build_incident_rag_context(
                    context,
                    fast_decision,
                    rag_retriever,
                    per_query_k=2,
                    top_k=5,
                    max_chars=3500,
                )
            )

            if rag_context.text:
                payload[
                    "retrieved_knowledge"
                ] = {
                    "role":
                        "reference_only",

                    "authority":
                        (
                            "No flight-control "
                            "authority"
                        ),

                    "context":
                        rag_context.text,

                    "chunk_ids":
                        list(
                            rag_context.chunk_ids
                        ),

                    "sources":
                        list(
                            rag_context.sources
                        ),

                    "sections":
                        list(
                            rag_context.sections
                        ),
                }

                rag_metadata[
                    "rag_used"
                ] = True

                rag_metadata[
                    "rag_chunk_ids"
                ] = list(
                    rag_context.chunk_ids
                )

                rag_metadata[
                    "rag_sources"
                ] = list(
                    rag_context.sources
                )

                rag_metadata[
                    "rag_sections"
                ] = list(
                    rag_context.sections
                )

        except Exception as rag_exc:
            # RAG is an advisory enhancement.
            #
            # Retrieval failure must never prevent
            # the Advisor from attempting its normal
            # explanation, and must never affect the
            # already-made flight decision.
            rag_metadata[
                "rag_error_type"
            ] = type(
                rag_exc
            ).__name__

            rag_metadata[
                "rag_error"
            ] = str(
                rag_exc
            )[:500]

        finally:
            rag_metadata[
                "rag_retrieval_latency_s"
            ] = (
                time.perf_counter()
                - rag_started
            )

    if client is None:
        client = get_mimo_client()

    if model is None:
        model = get_mimo_model()

    # OpenAI SDK normally retries failed requests.
    # For a runtime advisor we do not want long
    # retry chains.
    request_client = client

    if hasattr(
        client,
        "with_options",
    ):
        request_client = (
            client.with_options(
                timeout=ADVISOR_REQUEST_TIMEOUT_S,
                max_retries=0,
            )
        )

    try:
        response = (
            request_client
            .chat
            .completions
            .create(
                model=model,

                messages=[
                    {
                        "role": "system",
                        "content":
                            SYSTEM_PROMPT,
                    },
                    {
                        "role": "user",
                        "content": (
                            "Explain the following "
                            "completed deterministic "
                            "runtime decision:\n"
                            + json.dumps(
                                payload,
                                ensure_ascii=False,
                                separators=(
                                    ",",
                                    ":",
                                ),
                            )
                        ),
                    },
                ],

                tools=[
                    ADVISORY_TOOL
                ],

                tool_choice="required",

                max_completion_tokens=ADVISOR_MAX_COMPLETION_TOKENS,

                extra_body={
                    "thinking": {
                        "type": "disabled"
                    }
                },
            )
        )

        message = (
            response
            .choices[0]
            .message
        )

        tool_calls = (
            message.tool_calls
        )

        if not tool_calls:
            raise RuntimeError(
                "Advisor returned no "
                "tool call"
            )

        arguments = json.loads(
            tool_calls[0]
            .function
            .arguments
        )

        severity = (
            arguments["severity"]
        )

        if severity not in {
            "INFO",
            "WARNING",
            "CRITICAL",
        }:
            raise ValueError(
                "Invalid advisory severity"
            )

        confidence = float(
            arguments["confidence"]
        )

        if not (
            0.0
            <= confidence
            <= 1.0
        ):
            raise ValueError(
                "Advisor confidence "
                "outside [0,1]"
            )

        result = {
            "status":
                "COMPLETED",

            "advisory": {
                "severity":
                    severity,

                "diagnosis":
                    str(
                        arguments[
                            "diagnosis"
                        ]
                    )[:500],

                "decision_explanation":
                    str(
                        arguments[
                            "decision_explanation"
                        ]
                    )[:500],

                "recommended_followup":
                    str(
                        arguments[
                            "recommended_followup"
                        ]
                    )[:500],

                "confidence":
                    confidence,
            },

            # Keep the authoritative
            # deterministic decision alongside
            # the explanation.
            "observed_fast_decision":
                fast_decision.get(
                    "decision"
                ),

            "observed_selected_planner":
                fast_decision.get(
                    "selected_planner"
                ),

            "latency_s": (
                time.perf_counter()
                - start_time
            ),
        }

        result.update(
            rag_metadata
        )

        if verbose:
            print(
                "[INCIDENT ADVISOR] "
                f"status=COMPLETED, "
                f"severity={severity}, "
                f"latency="
                f"{result['latency_s']:.3f}s"
            )

        return result

    except Exception as exc:
        result = {
            "status":
                "FAILED",

            "error_type":
                type(exc).__name__,

            "error":
                str(exc)[:500],

            "observed_fast_decision":
                fast_decision.get(
                    "decision"
                ),

            "observed_selected_planner":
                fast_decision.get(
                    "selected_planner"
                ),

            "latency_s": (
                time.perf_counter()
                - start_time
            ),
        }

        result.update(
            rag_metadata
        )

        if verbose:
            print(
                "[INCIDENT ADVISOR] "
                f"status=FAILED, "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

        return result
