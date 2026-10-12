from typing import Literal

from pydantic import BaseModel, Field


# ============================================================
# Common types
# ============================================================

GridPoint = tuple[int, int]

MissionStatus = Literal[
    "PLANNED",
    "EXECUTING",
    "LANDING",
    "COMPLETED",
    "FAILED",
]

PlannerType = Literal[
    "normal",
    "communication_aware",
]


# ============================================================
# Mission schemas
# ============================================================

class MissionPlanRequest(BaseModel):
    start: GridPoint
    goal: GridPoint

    altitude_m: float = Field(
        default=5.0,
        gt=0.0,
        le=120.0,
    )

    planner: PlannerType = Field(
        default="normal",
        description=(
            "Path planner: normal or communication_aware"
        ),
    )

    communication_weight: float = Field(
        default=2.0,
        ge=0.0,
        le=20.0,
        description=(
            "Communication-risk weight used only "
            "by communication_aware planner"
        ),
    )


class PlannedWaypoint(BaseModel):
    index: int

    grid_x: int
    grid_y: int

    east_m: float
    north_m: float


class MissionPlanResponse(BaseModel):
    mission_id: str

    status: MissionStatus

    planner: str

    start: GridPoint
    goal: GridPoint

    altitude_m: float

    # Preserve the communication-risk weight
    # used when this mission was created.
    communication_weight: float = 2.0

    raw_path: list[GridPoint]

    waypoints: list[PlannedWaypoint]

    planned_distance_m: float


class MissionStatusResponse(BaseModel):
    mission_id: str

    status: MissionStatus

    planner: str

    planned_distance_m: float

    error_message: str | None = None


class MissionExecuteResponse(BaseModel):
    mission_id: str

    status: MissionStatus

    message: str


# ============================================================
# Radio Map schemas
# ============================================================

class RadioQueryRequest(BaseModel):
    east_m: float
    north_m: float

    altitude_m: float = Field(
        default=5.0,
        ge=0.0,
        le=120.0,
        description="UAV altitude in meters",
    )


class RadioQueryResponse(BaseModel):
    east_m: float
    north_m: float
    altitude_m: float

    serving_bs: str

    distance_m: float
    path_loss_db: float

    rsrp_dbm: float
    sinr_db: float

    coverage_score: float = Field(
        ge=0.0,
        le=1.0,
    )

    coverage_level: Literal[
        "GOOD",
        "FAIR",
        "POOR",
    ]


# ============================================================
# Route comparison schemas
# ============================================================

class MissionCompareRequest(BaseModel):
    start: GridPoint
    goal: GridPoint

    # Coordinate origin used by the Radio Map.
    # For initial planning this defaults to start.
    # For runtime replanning it should remain the
    # original mission start.
    radio_origin: GridPoint | None = None

    altitude_m: float = Field(
        default=5.0,
        gt=0.0,
        le=120.0,
    )

    communication_weight: float = Field(
        default=2.0,
        ge=0.0,
        le=20.0,
    )


class RouteOptionMetrics(BaseModel):
    planner: PlannerType

    raw_path: list[GridPoint]

    path_nodes: int
    planned_distance_m: float

    mean_coverage_score: float
    min_coverage_score: float

    mean_rsrp_dbm: float
    min_rsrp_dbm: float

    mean_sinr_db: float
    min_sinr_db: float

    handover_count: int


class MissionCompareResponse(BaseModel):
    start: GridPoint
    goal: GridPoint
    altitude_m: float
    communication_weight: float

    normal: RouteOptionMetrics

    communication_aware: RouteOptionMetrics
