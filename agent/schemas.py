from typing import Literal

from pydantic import BaseModel, Field


GridPoint = tuple[int, int]


class MissionIntent(BaseModel):
    """
    Structured mission intent produced by the LLM.
    """

    start: GridPoint

    goal: GridPoint

    altitude_m: float = Field(
        default=5.0,
        gt=0.0,
        le=120.0,
    )

    priority: Literal[
        "distance",
        "communication",
    ] = "distance"

    communication_weight: float = Field(
        default=2.0,
        ge=0.0,
        le=20.0,
    )

    execute: bool = False


class AgentMissionResult(BaseModel):
    mission_id: str

    status: str

    planner: str

    planned_distance_m: float

    start: GridPoint

    goal: GridPoint

    altitude_m: float

    message: str
