import json

from agent.incident_context import (
    IncidentContext,
)
from agent.incident_decision import (
    IncidentDecision,
    IncidentRouteSummary,
)
from agent.incident_tools import (
    compare_incident_routes,
)
from agent.llm_client import (
    get_mimo_client,
    get_mimo_model,
)


SYSTEM_PROMPT = """
You are the runtime Incident Agent for a low-altitude
UAV communication-aware scheduling platform.

You receive a structured communication incident context.

Your role is ONLY to diagnose the incident and recommend
whether the current route should be kept or whether a
communication-aware replan should be recommended.

You do NOT have permission to:
- arm a UAV
- take off
- land
- command PX4
- modify the active flight route
- claim that a route is safe or validated

Important rules:

1. All UAV position information is already calculated by
   deterministic code. Never infer or modify coordinates.

2. Route and communication metrics must come from tools.
   Never invent:
   - paths
   - distances
   - RSRP
   - SINR
   - coverage scores
   - handover counts

3. When comparing route options, consider:
   - remaining route distance
   - mean and minimum coverage score
   - mean and minimum RSRP
   - mean and minimum SINR
   - handover count

4. REPLAN_RECOMMENDED means:
   communication-aware replanning appears preferable based
   on the returned route metrics.

5. KEEP_ROUTE means:
   the evidence does not justify changing the current route.

6. A recommendation is NOT an execution command.

7. Do not claim collision avoidance, regulatory compliance,
   flight safety, or guaranteed communication quality unless
   a dedicated validation tool explicitly provides it.

8. The final reason must be one concise sentence,
   preferably under 160 characters.
"""


COMPARE_TOOL = {
    "type": "function",
    "function": {
        "name": "compare_remaining_routes",
        "description": (
            "Compare the remaining current-route option "
            "against communication-aware replanning using "
            "the bound runtime incident context."
        ),
        "parameters": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
}


DECISION_TOOL = {
    "type": "function",
    "function": {
        "name": "submit_incident_decision",
        "description": (
            "Submit the final structured incident "
            "recommendation after reading real route metrics."
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
                    "minLength": 1,
                    "maxLength": 200,
                    "description": (
                        "One concise sentence grounded in "
                        "the returned route metrics."
                    ),
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


def _route_summary(
    data: dict,
) -> IncidentRouteSummary:
    return IncidentRouteSummary(
        planner=data["planner"],
        planned_distance_m=(
            data["planned_distance_m"]
        ),
        mean_coverage_score=(
            data["mean_coverage_score"]
        ),
        min_coverage_score=(
            data["min_coverage_score"]
        ),
        mean_rsrp_dbm=(
            data["mean_rsrp_dbm"]
        ),
        min_rsrp_dbm=(
            data["min_rsrp_dbm"]
        ),
        mean_sinr_db=(
            data["mean_sinr_db"]
        ),
        min_sinr_db=(
            data["min_sinr_db"]
        ),
        handover_count=(
            data["handover_count"]
        ),
    )


def build_incident_decision(
    context: IncidentContext,
    comparison: dict,
    decision_arguments: dict,
) -> IncidentDecision:
    """
    Combine LLM high-level judgment with tool-grounded
    route metrics.

    The LLM is never allowed to provide metric values.
    """

    decision = (
        decision_arguments["decision"]
    )

    selected_planner = (
        decision_arguments[
            "selected_planner"
        ]
    )

    if decision == "KEEP_ROUTE":
        if selected_planner != context.planner:
            raise ValueError(
                "KEEP_ROUTE must preserve the "
                "current mission planner"
            )

    if decision == "REPLAN_RECOMMENDED":
        if (
            selected_planner
            != "communication_aware"
        ):
            raise ValueError(
                "REPLAN_RECOMMENDED must select "
                "communication_aware"
            )

    return IncidentDecision(
        decision=decision,
        selected_planner=selected_planner,
        reason=decision_arguments["reason"],
        normal=_route_summary(
            comparison["normal"]
        ),
        communication_aware=(
            _route_summary(
                comparison[
                    "communication_aware"
                ]
            )
        ),
    )


def _parse_single_tool_call(
    assistant_message,
    expected_name: str,
):
    tool_calls = (
        assistant_message.tool_calls
        or []
    )

    if len(tool_calls) != 1:
        raise RuntimeError(
            "Expected exactly one tool call, "
            f"received {len(tool_calls)}"
        )

    tool_call = tool_calls[0]

    if (
        tool_call.function.name
        != expected_name
    ):
        raise RuntimeError(
            "Unexpected tool call: "
            f"{tool_call.function.name}; "
            f"expected {expected_name}"
        )

    try:
        arguments = json.loads(
            tool_call.function.arguments
            or "{}"
        )
    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "Invalid JSON tool arguments: "
            f"{tool_call.function.arguments}"
        ) from exc

    return tool_call, arguments


def run_incident_agent(
    context: IncidentContext,
    verbose: bool = True,
) -> dict:
    """
    Runtime incident workflow:

    IncidentContext
        -> MiMo
        -> compare_remaining_routes
        -> real backend route metrics
        -> MiMo
        -> structured recommendation

    This function NEVER executes or modifies a flight.
    """

    client = get_mimo_client()
    model = get_mimo_model()

    context_json = json.dumps(
        context.to_dict(),
        ensure_ascii=False,
        indent=2,
    )

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": (
                "Analyze this runtime "
                "communication incident.\n\n"
                "Incident context:\n"
                f"{context_json}"
            ),
        },
    ]

    tool_trace = []

    # ==================================================
    # Round 1: force comparison tool
    # ==================================================

    response = (
        client.chat.completions.create(
            model=model,
            messages=messages,
            tools=[COMPARE_TOOL],
            tool_choice="required",
            max_completion_tokens=512,
            extra_body={
                "thinking": {
                    "type": "disabled"
                }
            },
        )
    )

    assistant_message = (
        response.choices[0].message
    )

    messages.append(
        assistant_message.model_dump(
            exclude_none=True
        )
    )

    tool_call, arguments = (
        _parse_single_tool_call(
            assistant_message,
            "compare_remaining_routes",
        )
    )

    if arguments:
        raise RuntimeError(
            "compare_remaining_routes "
            "must not receive arguments"
        )

    comparison = (
        compare_incident_routes(
            context
        )
    )

    tool_trace.append(
        {
            "tool":
                "compare_remaining_routes",
            "arguments": {},
            "result": comparison,
        }
    )

    if verbose:
        print()
        print(
            "[INCIDENT AGENT] "
            "Route comparison:"
        )
        print(
            json.dumps(
                comparison,
                ensure_ascii=False,
                indent=2,
            )
        )

    messages.append(
        {
            "role": "tool",
            "tool_call_id": tool_call.id,
            "content": json.dumps(
                comparison,
                ensure_ascii=False,
            ),
        }
    )

    # ==================================================
    # Round 2: force structured decision
    # ==================================================

    messages.append(
        {
            "role": "user",
            "content": (
                "Now submit exactly one structured "
                "incident decision using "
                "submit_incident_decision. "
                "Keep reason to one concise sentence "
                "under 160 characters."
            ),
        }
    )

    decision_arguments = None
    last_decision_error = None

    for attempt in range(1, 3):
        response = (
            client.chat.completions.create(
                model=model,
                messages=messages,
                tools=[DECISION_TOOL],
                tool_choice="required",
                max_completion_tokens=1024,
                extra_body={
                    "thinking": {
                        "type": "disabled"
                    }
                },
            )
        )

        finish_reason = (
            response.choices[0].finish_reason
        )

        assistant_message = (
            response.choices[0].message
        )

        if verbose:
            print(
                "[INCIDENT AGENT] "
                f"Decision attempt {attempt}, "
                f"finish_reason={finish_reason}"
            )

        try:
            _, decision_arguments = (
                _parse_single_tool_call(
                    assistant_message,
                    "submit_incident_decision",
                )
            )
            break

        except RuntimeError as exc:
            last_decision_error = exc

            if verbose:
                print(
                    "[INCIDENT AGENT] "
                    "Invalid decision tool output: "
                    f"{exc}"
                )

            if attempt >= 2:
                raise

            messages.append(
                {
                    "role": "user",
                    "content": (
                        "The previous decision tool "
                        "arguments were invalid or "
                        "truncated JSON. Retry once. "
                        "Call submit_incident_decision "
                        "with valid JSON only. "
                        "Keep reason under "
                        "160 characters."
                    ),
                }
            )

    if decision_arguments is None:
        raise RuntimeError(
            "Incident decision was not produced"
        ) from last_decision_error

    decision = build_incident_decision(
        context=context,
        comparison=comparison,
        decision_arguments=(
            decision_arguments
        ),
    )

    tool_trace.append(
        {
            "tool":
                "submit_incident_decision",
            "arguments":
                decision_arguments,
            "result":
                decision.model_dump(),
        }
    )

    if verbose:
        print()
        print(
            "[INCIDENT AGENT] Decision:"
        )
        print(
            json.dumps(
                decision.model_dump(),
                ensure_ascii=False,
                indent=2,
            )
        )

    return {
        "decision":
            decision.model_dump(),
        "tool_trace":
            tool_trace,
    }
