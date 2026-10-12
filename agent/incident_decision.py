from typing import Literal

from pydantic import (
    BaseModel,
    Field,
)


IncidentDecisionType = Literal[
    "KEEP_ROUTE",
    "REPLAN_RECOMMENDED",
]


class IncidentRouteSummary(BaseModel):
    planner: str

    planned_distance_m: float

    mean_coverage_score: float
    min_coverage_score: float

    mean_rsrp_dbm: float
    min_rsrp_dbm: float

    mean_sinr_db: float
    min_sinr_db: float

    handover_count: int


class IncidentDecision(BaseModel):
    decision: IncidentDecisionType

    selected_planner: Literal[
        "normal",
        "communication_aware",
    ]

    reason: str = Field(
        min_length=1,
        max_length=1000,
    )

    normal: IncidentRouteSummary
    communication_aware: IncidentRouteSummary
