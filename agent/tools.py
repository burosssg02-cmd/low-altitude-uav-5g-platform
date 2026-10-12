from backend.schemas import (
    MissionPlanRequest,
    RadioQueryRequest,
)

from backend.services.mission_service import (
    get_mission,
    plan_mission,
)

from backend.services.radio_service import (
    query_radio_map,
)

from agent.schemas import (
    AgentMissionResult,
    MissionIntent,
)


# ============================================================
# Radio Map Tool
# ============================================================

def radio_query_tool(
    east_m: float,
    north_m: float,
    altitude_m: float = 5.0,
) -> dict:
    """
    Query 5G communication quality
    at one UAV position.
    """

    request = RadioQueryRequest(
        east_m=east_m,
        north_m=north_m,
        altitude_m=altitude_m,
    )

    result = query_radio_map(
        request
    )

    return result.model_dump()


# ============================================================
# Mission Planning Tool
# ============================================================

def mission_plan_tool(
    intent: MissionIntent,
) -> AgentMissionResult:
    """
    Convert a structured mission intent
    into a backend mission.
    """

    if intent.priority == "communication":

        planner = (
            "communication_aware"
        )

    else:

        planner = "normal"

    request = MissionPlanRequest(
        start=intent.start,
        goal=intent.goal,
        altitude_m=intent.altitude_m,
        planner=planner,
        communication_weight=(
            intent.communication_weight
        ),
    )

    mission = plan_mission(
        request
    )

    if planner == "communication_aware":
        message = (
            "Communication-aware mission planned "
            "with 5G coverage considered."
        )
    else:
        message = (
            "Distance-priority mission planned "
            "with normal A*."
        )

    return AgentMissionResult(
        mission_id=mission.mission_id,
        status=mission.status,
        planner=mission.planner,
        planned_distance_m=(
            mission.planned_distance_m
        ),
        start=mission.start,
        goal=mission.goal,
        altitude_m=mission.altitude_m,
        message=message,
    )


# ============================================================
# Mission Status Tool
# ============================================================

def mission_status_tool(
    mission_id: str,
) -> dict:
    """
    Query current mission state.
    """

    result = get_mission(
        mission_id
    )

    return result.model_dump()
