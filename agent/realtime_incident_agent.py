import json
import time

from agent.incident_tools import (
    compare_incident_routes,
)
from agent.llm_client import (
    get_mimo_client,
    get_mimo_model,
)


SYSTEM_PROMPT = """
You are the real-time communication Incident Agent
for a low-altitude UAV platform.

A deterministic route comparison has already been
performed before you are called.

Your job is ONLY to make one high-level decision.

Allowed decisions:

1. KEEP_ROUTE
   - Keep the UAV's current planner.
   - selected_planner must equal the current planner.

2. REPLAN_RECOMMENDED
   - Recommend switching to the
     communication_aware planner.
   - selected_planner must be communication_aware.

Use the supplied route metrics as authoritative data.

Prefer REPLAN_RECOMMENDED when the
communication-aware route gives a meaningful
communication improvement without an unreasonable
distance penalty.

Do not invent route metrics.
Do not call any route-comparison tool.
Keep the reason concise.
"""


DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_incident_decision",
        "description": (
            "Submit the real-time incident decision."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "decision": {
                    "type": "string",
                    "enum": [
                        "KEEP_ROUTE",
                        "REPLAN_RECOMMENDED",
                    ],
                },
                "selected_planner": {
                    "type": "string",
                    "enum": [
                        "normal",
                        "communication_aware",
                    ],
                },
                "reason": {
                    "type": "string",
                },
            },
            "required": [
                "decision",
                "selected_planner",
                "reason",
            ],
            "additionalProperties": False,
        },
    },
}


def _compact_metrics(
    route: dict,
) -> dict:
    """
    Keep only metrics needed by the runtime decision.
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


def _safe_fallback(
    *,
    context,
    comparison: dict,
    reason: str,
) -> dict:
    """
    Fail-safe behavior:
    if the LLM response is invalid, keep the
    current route rather than issuing an
    unvalidated replan.
    """

    normal = _compact_metrics(
        comparison["normal"]
    )

    communication_aware = (
        _compact_metrics(
            comparison[
                "communication_aware"
            ]
        )
    )

    return {
        "decision": {
            "decision": "KEEP_ROUTE",
            "selected_planner": (
                context.planner
            ),
            "reason": reason,
            "normal": normal,
            "communication_aware": (
                communication_aware
            ),
        },
        "fallback_used": True,
    }


def run_realtime_incident_agent(
    context,
    verbose: bool = False,
    *,
    client=None,
    model=None,
    compare_runner=compare_incident_routes,
) -> dict:
    """
    Real-time Incident Agent.

    Important design:
    route comparison is deterministic and occurs
    BEFORE the single LLM request.

    Therefore the LLM no longer spends one round
    deciding whether it should call the comparison
    tool.
    """

    total_start = time.perf_counter()

    # ==================================================
    # 1. Deterministic comparison first
    # ==================================================

    compare_start = time.perf_counter()

    comparison = compare_runner(
        context
    )

    compare_latency_s = (
        time.perf_counter()
        - compare_start
    )

    normal = _compact_metrics(
        comparison["normal"]
    )

    communication_aware = (
        _compact_metrics(
            comparison[
                "communication_aware"
            ]
        )
    )

    # ==================================================
    # 2. Build compact one-shot prompt
    # ==================================================

    payload = {
        "incident": {
            "mission_id":
                context.mission_id,

            "current_planner":
                context.planner,

            "current_grid":
                context.current_grid,

            "goal":
                context.mission_goal,

            "rsrp_dbm":
                context.rsrp_dbm,

            "sinr_db":
                context.sinr_db,

            "coverage_score":
                context.coverage_score,

            "reasons":
                context.reasons,
        },

        "normal":
            normal,

        "communication_aware":
            communication_aware,
    }

    user_text = (
        "Make exactly one runtime decision "
        "from the following deterministic "
        "incident analysis:\n"
        + json.dumps(
            payload,
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )

    if client is None:
        client = get_mimo_client()

    if model is None:
        model = get_mimo_model()

    # ==================================================
    # 3. ONE LLM call only
    # ==================================================

    llm_start = time.perf_counter()

    try:
        response = (
            client.chat.completions.create(
                model=model,

                messages=[
                    {
                        "role": "system",
                        "content": (
                            SYSTEM_PROMPT
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            user_text
                        ),
                    },
                ],

                tools=[
                    DECISION_TOOL
                ],

                # Only one tool exists.
                # The model must submit the decision.
                tool_choice="required",

                max_completion_tokens=256,

                # The runtime decision must not
                # block the flight loop indefinitely.
                timeout=5.0,

                extra_body={
                    "thinking": {
                        "type": "disabled"
                    }
                },
            )
        )

        llm_latency_s = (
            time.perf_counter()
            - llm_start
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
                "LLM returned no decision "
                "tool call"
            )

        arguments = json.loads(
            tool_calls[0]
            .function
            .arguments
        )

        decision = arguments[
            "decision"
        ]

        selected_planner = (
            arguments[
                "selected_planner"
            ]
        )

        reason = (
            str(
                arguments["reason"]
            )
            [:200]
        )

        # ==============================================
        # Deterministic validation
        # ==============================================

        if (
            decision
            == "KEEP_ROUTE"
        ):
            if (
                selected_planner
                != context.planner
            ):
                raise ValueError(
                    "KEEP_ROUTE must preserve "
                    "the current planner"
                )

        elif (
            decision
            == "REPLAN_RECOMMENDED"
        ):
            if (
                selected_planner
                != "communication_aware"
            ):
                raise ValueError(
                    "REPLAN_RECOMMENDED must "
                    "select communication_aware"
                )

        else:
            raise ValueError(
                "Unsupported decision"
            )

        total_latency_s = (
            time.perf_counter()
            - total_start
        )

        result = {
            "decision": {
                "decision":
                    decision,

                "selected_planner":
                    selected_planner,

                "reason":
                    reason,

                # These values always come from the
                # deterministic comparison, never
                # from the LLM.
                "normal":
                    normal,

                "communication_aware":
                    communication_aware,
            },

            "fallback_used":
                False,

            "latency": {
                "compare_s":
                    compare_latency_s,

                "llm_s":
                    llm_latency_s,

                "total_s":
                    total_latency_s,
            },
        }

        if verbose:
            print(
                "[REALTIME INCIDENT] "
                f"decision={decision}"
            )

            print(
                "[REALTIME INCIDENT] "
                f"compare="
                f"{compare_latency_s:.3f}s, "
                f"llm="
                f"{llm_latency_s:.3f}s, "
                f"total="
                f"{total_latency_s:.3f}s"
            )

        return result

    except Exception as exc:
        llm_latency_s = (
            time.perf_counter()
            - llm_start
        )

        result = _safe_fallback(
            context=context,
            comparison=comparison,
            reason=(
                "Real-time Agent failed; "
                "safe fallback keeps the "
                "current route. "
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        )

        result["latency"] = {
            "compare_s":
                compare_latency_s,

            "llm_s":
                llm_latency_s,

            "total_s": (
                time.perf_counter()
                - total_start
            ),
        }

        if verbose:
            print(
                "[REALTIME INCIDENT] "
                "safe fallback KEEP_ROUTE"
            )

            print(
                "[REALTIME INCIDENT] "
                f"{type(exc).__name__}: "
                f"{exc}"
            )

        return result
