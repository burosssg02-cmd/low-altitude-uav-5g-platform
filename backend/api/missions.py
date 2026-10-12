from fastapi import (
    APIRouter,
    BackgroundTasks,
    HTTPException,
)

from backend.schemas import (
    MissionCompareRequest,
    MissionCompareResponse,
    MissionExecuteResponse,
    MissionPlanRequest,
    MissionPlanResponse,
    MissionStatusResponse,
)

from backend.services.mission_service import (
    compare_route_options,
    get_mission,
    get_mission_plan,
    plan_mission,
    update_mission_status,
)

from uav_runtime.mission_executor import (
    execute_mission,
)


router = APIRouter(
    prefix="/missions",
    tags=["missions"],
)


async def run_mission_in_background(
    mission_id: str,
):
    """
    Run PX4 mission without blocking
    the HTTP response.
    """

    try:
        await execute_mission(
            mission_id
        )

    except Exception as exc:
        # execute_mission normally marks
        # the mission FAILED itself.
        # This prevents the background
        # exception from propagating.
        print(
            f"[API] Mission {mission_id} "
            f"background task failed: {exc}"
        )


@router.post(
    "/plan",
    response_model=MissionPlanResponse,
)
async def create_mission_plan(
    request: MissionPlanRequest,
):
    return plan_mission(
        request
    )


@router.post(
    "/{mission_id}/execute",
    response_model=MissionExecuteResponse,
)
async def execute_planned_mission(
    mission_id: str,
    background_tasks: BackgroundTasks,
):
    mission = get_mission_plan(
        mission_id
    )

    if mission.status != "PLANNED":
        raise HTTPException(
            status_code=409,
            detail=(
                f"Mission cannot execute "
                f"from status "
                f"{mission.status}"
            ),
        )

    # Reserve the mission immediately.
    # This prevents duplicate execution.
    update_mission_status(
        mission_id,
        "EXECUTING",
    )

    background_tasks.add_task(
        run_mission_in_background,
        mission_id,
    )

    return MissionExecuteResponse(
        mission_id=mission_id,
        status="EXECUTING",
        message=(
            "Mission accepted and "
            "execution started."
        ),
    )


@router.get(
    "/{mission_id}",
    response_model=MissionStatusResponse,
)
async def read_mission(
    mission_id: str,
):
    return get_mission(
        mission_id
    )


@router.post(
    "/compare",
    response_model=MissionCompareResponse,
)
async def compare_mission_routes(
    request: MissionCompareRequest,
):
    """
    Compare normal and communication-aware
    route options without creating a mission.
    """

    return compare_route_options(
        request
    )
