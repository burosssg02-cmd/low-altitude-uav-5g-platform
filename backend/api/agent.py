from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
)

from pydantic import (
    BaseModel,
    Field,
)

from starlette.concurrency import (
    run_in_threadpool,
)

from agent.tool_calling_agent import (
    run_tool_calling_agent,
)


router = APIRouter(
    prefix="/agent",
    tags=["agent"],
)


class AgentChatRequest(BaseModel):
    message: str = Field(
        min_length=1,
        max_length=2000,
        description=(
            "Natural-language UAV mission request"
        ),
    )


class AgentChatResponse(BaseModel):
    answer: str

    tool_trace: list[
        dict[str, Any]
    ]


@router.post(
    "/chat",
    response_model=AgentChatResponse,
)
async def agent_chat(
    request: AgentChatRequest,
):
    """
    Natural language
        -> MiMo Agent
        -> Tool Calling
        -> FastAPI mission/radio tools
        -> grounded response
    """

    try:
        result = await run_in_threadpool(
            run_tool_calling_agent,
            request.message,
            False,
        )

    except Exception as exc:
        raise HTTPException(
            status_code=500,
            detail=(
                f"Agent failed: "
                f"{type(exc).__name__}: "
                f"{exc}"
            ),
        ) from exc

    return AgentChatResponse(
        answer=result["answer"],
        tool_trace=result[
            "tool_trace"
        ],
    )
