import json

from agent.llm_client import (
    get_mimo_client,
    get_mimo_model,
)

from agent.http_tools import (
    mission_plan_api_tool,
    mission_status_api_tool,
    radio_query_api_tool,
    route_compare_api_tool,
)


SYSTEM_PROMPT = """
You are the Mission Agent for a low-altitude UAV
communication-aware scheduling platform.

You can use tools to:

1. plan UAV missions
2. query 5G radio coverage
3. query mission status

Important rules:

- Use plan_mission when the user asks to plan a route.
- Use query_radio_map when the user asks about signal,
  RSRP, SINR, coverage, or communication quality.
- Use get_mission_status when the user asks about an
  existing mission.

Decision workflow:

- Use compare_route_options when the user asks you
  to compare route strategies, choose between distance
  and communication quality, or make a trade-off.

- Examples include:
  "帮我判断走哪条更合适"
  "距离可以长一点，但信号不能太差"
  "比较两种方案"
  "兼顾距离和通信"
  "你帮我选择"

- For these trade-off requests:
  1. First call compare_route_options.
  2. Read the real comparison metrics.
  3. Choose a planner based on the user's stated preference.
  4. Then call plan_mission using:
     priority = "distance"
     or
     priority = "communication".

- compare_route_options only analyzes alternatives.
  It does NOT create a mission.

Mission planning priorities:

- shortest distance / 最短距离 / 距离优先
  -> priority = distance

- communication / signal / coverage / 通信优先 /
  保证通信质量 / 避免弱覆盖
  -> priority = communication

If communication priority is requested and the user
does not specify communication_weight, use 2.0.

Never invent missing start or goal coordinates.

This Agent currently supports mission planning only.
It does NOT have permission to arm, take off, land,
or execute a UAV mission.

Never claim that a UAV has actually flown unless
a future execution tool explicitly reports it.

Ground all mission facts in tool results.

Never invent or infer:
- mission IDs
- routes
- distances
- mission states
- RSRP values
- SINR values
- coverage scores
- communication quality guarantees

A communication-aware route means that communication
quality was considered during optimization. It does NOT
by itself guarantee good communication quality.

Only report communication-quality measurements when
they are explicitly returned by a tool.

Route-grounding rules:

- Grid x increasing means east.
- Grid x decreasing means west.
- Grid y increasing means south.
- Grid y decreasing means north.

Do not add cardinal-direction descriptions to a route
unless they are directly derived from the returned
coordinates.

Prefer listing waypoint coordinates without adding
direction labels.

Do not claim that a route is safe, validated, collision-free,
or guaranteed to avoid hazards unless a safety-validation
tool explicitly reports that result.

Do not add engineering conclusions that are not present
in tool results.
"""


TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "plan_mission",
            "description": (
                "Plan a UAV route through the "
                "mission backend."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "minItems": 2,
                        "maxItems": 2,
                        "description": (
                            "Start grid coordinate [x, y]"
                        ),
                    },
                    "goal": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "minItems": 2,
                        "maxItems": 2,
                        "description": (
                            "Goal grid coordinate [x, y]"
                        ),
                    },
                    "altitude_m": {
                        "type": "number",
                        "description": (
                            "Flight altitude in meters"
                        ),
                        "default": 5.0,
                    },
                    "priority": {
                        "type": "string",
                        "enum": [
                            "distance",
                            "communication",
                        ],
                        "description": (
                            "Route optimization priority"
                        ),
                    },
                    "communication_weight": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 20.0,
                        "default": 2.0,
                        "description": (
                            "Communication risk weight"
                        ),
                    },
                },
                "required": [
                    "start",
                    "goal",
                    "priority",
                ],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "query_radio_map",
            "description": (
                "Query predicted 5G radio quality "
                "at a UAV position."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "east_m": {
                        "type": "number",
                    },
                    "north_m": {
                        "type": "number",
                    },
                    "altitude_m": {
                        "type": "number",
                        "default": 5.0,
                    },
                },
                "required": [
                    "east_m",
                    "north_m",
                ],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "compare_route_options",
            "description": (
                "Compare normal A* and "
                "communication-aware A* using "
                "real route and radio metrics. "
                "This does not create a mission."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "start": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "minItems": 2,
                        "maxItems": 2,
                        "description": (
                            "Start grid coordinate [x, y]"
                        ),
                    },
                    "goal": {
                        "type": "array",
                        "items": {
                            "type": "integer"
                        },
                        "minItems": 2,
                        "maxItems": 2,
                        "description": (
                            "Goal grid coordinate [x, y]"
                        ),
                    },
                    "altitude_m": {
                        "type": "number",
                        "default": 5.0,
                    },
                    "communication_weight": {
                        "type": "number",
                        "minimum": 0.0,
                        "maximum": 20.0,
                        "default": 2.0,
                    },
                },
                "required": [
                    "start",
                    "goal",
                ],
                "additionalProperties": False,
            },
        },
    },

    {
        "type": "function",
        "function": {
            "name": "get_mission_status",
            "description": (
                "Get the current state of an "
                "existing UAV mission."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "mission_id": {
                        "type": "string",
                    },
                },
                "required": [
                    "mission_id",
                ],
                "additionalProperties": False,
            },
        },
    },
]


def execute_tool(
    tool_name: str,
    arguments: dict,
) -> dict:
    """
    Dispatch one model-requested tool call
    to the FastAPI-based tool layer.
    """

    if tool_name == "plan_mission":
        return mission_plan_api_tool(
            start=arguments["start"],
            goal=arguments["goal"],
            altitude_m=arguments.get(
                "altitude_m",
                5.0,
            ),
            priority=arguments[
                "priority"
            ],
            communication_weight=(
                arguments.get(
                    "communication_weight",
                    2.0,
                )
            ),
        )

    if tool_name == "query_radio_map":
        return radio_query_api_tool(
            east_m=arguments[
                "east_m"
            ],
            north_m=arguments[
                "north_m"
            ],
            altitude_m=arguments.get(
                "altitude_m",
                5.0,
            ),
        )

    if tool_name == "compare_route_options":
        return route_compare_api_tool(
            start=arguments["start"],
            goal=arguments["goal"],
            altitude_m=arguments.get(
                "altitude_m",
                5.0,
            ),
            communication_weight=(
                arguments.get(
                    "communication_weight",
                    2.0,
                )
            ),
        )

    if tool_name == "get_mission_status":
        return mission_status_api_tool(
            mission_id=arguments[
                "mission_id"
            ]
        )

    raise ValueError(
        f"Unknown tool: {tool_name}"
    )


def run_tool_calling_agent(
    user_text: str,
    verbose: bool = True,
) -> dict:
    """
    User natural language
        -> MiMo
        -> tool call
        -> FastAPI
        -> tool result
        -> MiMo final response
    """

    if not user_text.strip():
        raise ValueError(
            "User text must not be empty"
        )

    client = get_mimo_client()
    model = get_mimo_model()

    messages = [
        {
            "role": "system",
            "content": SYSTEM_PROMPT,
        },
        {
            "role": "user",
            "content": user_text,
        },
    ]

    tool_trace = []

    # Prevent accidental infinite
    # model-tool loops.
    max_rounds = 6

    for round_index in range(
        1,
        max_rounds + 1,
    ):
        response = (
            client.chat.completions.create(
                model=model,
                messages=messages,
                tools=TOOLS,
                tool_choice=(
                    "required"
                    if round_index == 1
                    else "auto"
                ),
                max_completion_tokens=1024,
                extra_body={
                    "thinking": {
                        "type": "disabled"
                    }
                },
            )
        )

        assistant_message = (
            response
            .choices[0]
            .message
        )

        messages.append(
            assistant_message.model_dump(
                exclude_none=True
            )
        )

        tool_calls = (
            assistant_message.tool_calls
        )

        # ================================================
        # Final natural-language answer
        # ================================================

        if not tool_calls:

            final_answer = (
                assistant_message.content
                or ""
            )

            if verbose:
                print()
                print(
                    "[AGENT] Final answer:"
                )
                print(
                    final_answer
                )

            return {
                "answer":
                    final_answer,

                "tool_trace":
                    tool_trace,
            }

        # ================================================
        # Execute requested tools
        # ================================================

        for tool_call in tool_calls:

            tool_name = (
                tool_call.function.name
            )

            raw_arguments = (
                tool_call
                .function
                .arguments
            )

            try:
                arguments = json.loads(
                    raw_arguments
                )

            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    "Invalid tool arguments "
                    f"from LLM: "
                    f"{raw_arguments}"
                ) from exc

            if verbose:
                print()
                print(
                    f"[AGENT] Tool call "
                    f"round {round_index}: "
                    f"{tool_name}"
                )

                print(
                    "[AGENT] Arguments:"
                )

                print(
                    json.dumps(
                        arguments,
                        ensure_ascii=False,
                        indent=2,
                    )
                )

            try:
                result = execute_tool(
                    tool_name,
                    arguments,
                )

            except Exception as exc:
                result = {
                    "error": (
                        f"{type(exc).__name__}: "
                        f"{exc}"
                    )
                }

            tool_trace.append(
                {
                    "tool":
                        tool_name,

                    "arguments":
                        arguments,

                    "result":
                        result,
                }
            )

            if verbose:
                print(
                    "[AGENT] Tool result:"
                )

                print(
                    json.dumps(
                        result,
                        ensure_ascii=False,
                        indent=2,
                    )
                )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id":
                        tool_call.id,

                    "content":
                        json.dumps(
                            result,
                            ensure_ascii=False,
                        ),
                }
            )

    raise RuntimeError(
        "Agent exceeded maximum "
        "tool-call rounds"
    )
