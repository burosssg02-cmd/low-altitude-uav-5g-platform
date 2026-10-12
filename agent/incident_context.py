from dataclasses import (
    asdict,
    dataclass,
)

from planner.coordinate_converter import (
    local_to_grid,
)


@dataclass
class IncidentContext:
    """
    Structured context for a runtime
    communication incident.

    All position conversion is deterministic.
    The LLM must not infer the UAV grid position.
    """

    incident_type: str
    mission_id: str

    mission_start: tuple[int, int]
    mission_goal: tuple[int, int]

    current_grid: tuple[int, int]

    east_m: float
    north_m: float
    altitude_m: float

    rsrp_dbm: float
    sinr_db: float
    coverage_score: float

    serving_bs: str | None

    reasons: list[str]

    planner: str
    communication_weight: float


    def to_dict(self) -> dict:
        return asdict(self)


def build_incident_context(
    *,
    event: dict,
    mission_id: str,
    mission_start: tuple[int, int],
    mission_goal: tuple[int, int],
    planner: str,
    altitude_m: float,
    communication_weight: float = 2.0,
    grid_resolution_m: float = 5.0,
) -> IncidentContext:
    """
    Convert a runtime communication event into
    deterministic structured Agent context.
    """

    required_event_fields = [
        "event_type",
        "east_m",
        "north_m",
        "rsrp_dbm",
        "sinr_db",
        "coverage_score",
    ]

    missing = [
        field
        for field in required_event_fields
        if field not in event
    ]

    if missing:
        raise ValueError(
            "Incident event missing fields: "
            f"{missing}"
        )

    current_grid = local_to_grid(
        east_m=float(
            event["east_m"]
        ),
        north_m=float(
            event["north_m"]
        ),
        origin_node=mission_start,
        resolution_m=grid_resolution_m,
    )

    return IncidentContext(
        incident_type=str(
            event["event_type"]
        ),

        mission_id=mission_id,

        mission_start=mission_start,
        mission_goal=mission_goal,

        current_grid=current_grid,

        east_m=float(
            event["east_m"]
        ),
        north_m=float(
            event["north_m"]
        ),
        altitude_m=float(
            event.get(
                "altitude_m",
                altitude_m,
            )
        ),

        rsrp_dbm=float(
            event["rsrp_dbm"]
        ),
        sinr_db=float(
            event["sinr_db"]
        ),
        coverage_score=float(
            event["coverage_score"]
        ),

        serving_bs=event.get(
            "serving_bs"
        ),

        reasons=list(
            event.get(
                "reasons",
                [],
            )
        ),

        planner=planner,

        communication_weight=(
            communication_weight
        ),
    )
