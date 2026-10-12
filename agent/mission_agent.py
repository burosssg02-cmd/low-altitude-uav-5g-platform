import json

from pydantic import ValidationError

from agent.llm_client import (
    get_mimo_client,
    get_mimo_model,
)

from agent.schemas import (
    MissionIntent,
)

from agent.tools import (
    mission_plan_tool,
)


SYSTEM_PROMPT = """
You are the mission-intent parser for a low-altitude UAV
communication-aware scheduling platform.

Your task is to convert the user's natural-language UAV
mission request into exactly one JSON object.

Required JSON format:

{
  "start": [x, y],
  "goal": [x, y],
  "altitude_m": 5.0,
  "priority": "distance" or "communication",
  "communication_weight": 2.0,
  "execute": false
}

Rules:

1. start and goal are integer grid coordinates.
2. altitude_m must be a positive number.
3. If the user says:
   - shortest
   - minimum distance
   - distance first
   - 最短
   - 距离优先

   use:
   "priority": "distance"

4. If the user says:
   - communication
   - coverage
   - signal
   - RSRP
   - SINR
   - avoid weak coverage
   - 通信
   - 信号
   - 覆盖
   - 避免弱覆盖
   - 保证通信质量
   - 通信优先

   use:
   "priority": "communication"

5. If communication priority is requested and no weight
   is specified, use communication_weight = 2.0.

6. Never set execute=true unless the user explicitly asks
   to execute, launch, fly, start the mission, or 起飞/执行任务.

7. For this version, even if execution is requested,
   keep execute=false. Actual flight execution requires
   a separate confirmation step.

8. Do not invent missing start or goal coordinates.

9. Return JSON only.
Do not include Markdown.
Do not include explanation.
"""


def parse_mission_intent(
    user_text: str,
) -> MissionIntent:
    """
    Use MiMo to convert natural language
    into validated MissionIntent.
    """

    if not user_text.strip():
        raise ValueError(
            "Mission text must not be empty"
        )

    client = get_mimo_client()

    model = get_mimo_model()

    response = (
        client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "system",
                    "content": SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": user_text,
                },
            ],
            max_completion_tokens=512,
            extra_body={
                "thinking": {
                    "type": "disabled"
                }
            },
        )
    )

    content = (
        response
        .choices[0]
        .message
        .content
    )

    if not content:
        raise RuntimeError(
            "LLM returned empty content"
        )

    content = content.strip()

    # Defensive cleanup in case a model
    # wraps JSON in Markdown.
    if content.startswith("```"):
        lines = content.splitlines()

        if (
            lines
            and lines[0].startswith("```")
        ):
            lines = lines[1:]

        if (
            lines
            and lines[-1].strip()
            == "```"
        ):
            lines = lines[:-1]

        content = "\n".join(
            lines
        ).strip()

        if content.startswith("json"):
            content = (
                content[4:]
                .strip()
            )

    try:
        data = json.loads(
            content
        )

    except json.JSONDecodeError as exc:
        raise RuntimeError(
            "LLM did not return valid JSON. "
            f"Raw response: {content}"
        ) from exc

    # Safety rule:
    # V0.6.2 is planning-only.
    data["execute"] = False

    try:
        return MissionIntent(
            **data
        )

    except ValidationError as exc:
        raise RuntimeError(
            "LLM returned invalid mission intent. "
            f"Data: {data}"
        ) from exc


def run_mission_agent(
    user_text: str,
):
    """
    Natural language
        -> MissionIntent
        -> mission_plan_tool
        -> mission result
    """

    intent = parse_mission_intent(
        user_text
    )

    mission = mission_plan_tool(
        intent
    )

    return {
        "user_text":
            user_text,

        "intent":
            intent.model_dump(),

        "mission":
            mission.model_dump(),
    }
