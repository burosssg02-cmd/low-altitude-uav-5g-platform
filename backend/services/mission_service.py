import math
import uuid

from communication.radio_map import (
    build_demo_radio_map,
)

from planner.astar import (
    astar_search,
)

from planner.communication_astar import (
    communication_astar_search,
    evaluate_grid_path,
)

from planner.coordinate_converter import (
    grid_to_local,
)

from planner.grid_map import (
    GridMap,
)

from planner.path_utils import (
    simplify_path,
)

from backend.schemas import (
    MissionCompareRequest,
    MissionCompareResponse,
    MissionPlanRequest,
    MissionPlanResponse,
    RouteOptionMetrics,
    MissionStatus,
    MissionStatusResponse,
    PlannedWaypoint,
)


# ============================================================
# Demo environment configuration
# ============================================================

GRID_WIDTH = 10
GRID_HEIGHT = 8

GRID_RESOLUTION_M = 5.0


OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


# ============================================================
# Runtime state
# ============================================================

MISSIONS: dict[
    str,
    MissionPlanResponse,
] = {}


MISSION_ERRORS: dict[
    str,
    str | None,
] = {}


RADIO_MAP = (
    build_demo_radio_map()
)


# ============================================================
# Helpers
# ============================================================

def calculate_path_distance_m(
    waypoints: list[PlannedWaypoint],
) -> float:

    total_distance = 0.0

    for index in range(
        1,
        len(waypoints),
    ):

        previous = (
            waypoints[index - 1]
        )

        current = (
            waypoints[index]
        )

        delta_east = (
            current.east_m
            - previous.east_m
        )

        delta_north = (
            current.north_m
            - previous.north_m
        )

        total_distance += math.sqrt(
            delta_east ** 2
            + delta_north ** 2
        )

    return total_distance


def build_waypoints(
    path,
    start,
) -> list[PlannedWaypoint]:

    waypoints = []

    for index, node in enumerate(
        path
    ):

        east_m, north_m = (
            grid_to_local(
                node=node,
                origin_node=start,
                resolution_m=(
                    GRID_RESOLUTION_M
                ),
            )
        )

        waypoints.append(
            PlannedWaypoint(
                index=index,
                grid_x=node[0],
                grid_y=node[1],
                east_m=east_m,
                north_m=north_m,
            )
        )

    return waypoints


# ============================================================
# Mission planning
# ============================================================

def plan_mission(
    request: MissionPlanRequest,
) -> MissionPlanResponse:

    grid_map = GridMap(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        obstacles=OBSTACLES,
    )

    # --------------------------------------------------------
    # Planner selection
    # --------------------------------------------------------

    if request.planner == "normal":

        raw_path = astar_search(
            grid_map,
            request.start,
            request.goal,
        )

        planner_name = (
            "normal"
        )

    elif (
        request.planner
        == "communication_aware"
    ):

        raw_path = (
            communication_astar_search(
                grid_map=grid_map,
                start=request.start,
                goal=request.goal,
                radio_map=RADIO_MAP,
                altitude_m=request.altitude_m,
                resolution_m=(
                    GRID_RESOLUTION_M
                ),
                communication_weight=(
                    request.communication_weight
                ),
                radio_origin=radio_origin,
            )
        )

        planner_name = (
            "communication_aware"
        )

    else:
        raise ValueError(
            f"Unsupported planner: "
            f"{request.planner}"
        )

    # --------------------------------------------------------
    # Path simplification
    # --------------------------------------------------------

    simplified_path = (
        simplify_path(
            raw_path
        )
    )

    waypoints = (
        build_waypoints(
            simplified_path,
            request.start,
        )
    )

    planned_distance_m = (
        calculate_path_distance_m(
            waypoints
        )
    )

    # --------------------------------------------------------
    # Create mission
    # --------------------------------------------------------

    mission_id = (
        "mission_"
        + uuid.uuid4().hex[:12]
    )

    mission = MissionPlanResponse(
        mission_id=mission_id,

        status="PLANNED",

        planner=planner_name,

        start=request.start,
        goal=request.goal,

        altitude_m=(
            request.altitude_m
        ),

        communication_weight=(
            request.communication_weight
        ),

        raw_path=raw_path,

        waypoints=waypoints,

        planned_distance_m=(
            planned_distance_m
        ),
    )

    MISSIONS[
        mission_id
    ] = mission

    MISSION_ERRORS[
        mission_id
    ] = None

    return mission


# ============================================================
# Mission state management
# ============================================================

def get_mission_plan(
    mission_id: str,
) -> MissionPlanResponse:

    mission = MISSIONS.get(
        mission_id
    )

    if mission is None:
        raise KeyError(
            f"Mission not found: "
            f"{mission_id}"
        )

    return mission


def update_mission_status(
    mission_id: str,
    status: MissionStatus,
    error_message: str | None = None,
) -> MissionPlanResponse:

    mission = get_mission_plan(
        mission_id
    )

    updated_mission = (
        mission.model_copy(
            update={
                "status": status,
            }
        )
    )

    MISSIONS[
        mission_id
    ] = updated_mission

    MISSION_ERRORS[
        mission_id
    ] = error_message

    print(
        f"[MISSION] "
        f"{mission_id}: "
        f"{mission.status} "
        f"-> {status}"
    )

    return updated_mission


def get_mission(
    mission_id: str,
) -> MissionStatusResponse:

    mission = get_mission_plan(
        mission_id
    )

    return MissionStatusResponse(
        mission_id=(
            mission.mission_id
        ),

        status=(
            mission.status
        ),

        planner=(
            mission.planner
        ),

        planned_distance_m=(
            mission.planned_distance_m
        ),

        error_message=(
            MISSION_ERRORS.get(
                mission_id
            )
        ),
    )


# ============================================================
# Route comparison
# ============================================================

def compare_route_options(
    request: MissionCompareRequest,
) -> MissionCompareResponse:
    """
    Compare normal A* and communication-aware A*
    without creating or executing a mission.
    """

    grid_map = GridMap(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        obstacles=OBSTACLES,
    )

    radio_origin = (
        request.radio_origin
        if request.radio_origin is not None
        else request.start
    )

    # --------------------------------------------------------
    # 1. Normal A*
    # --------------------------------------------------------

    normal_path = astar_search(
        grid_map,
        request.start,
        request.goal,
    )

    normal_metrics = evaluate_grid_path(
        path=normal_path,
        start=request.start,
        radio_map=RADIO_MAP,
        altitude_m=request.altitude_m,
        resolution_m=GRID_RESOLUTION_M,
        radio_origin=radio_origin,
    )

    # --------------------------------------------------------
    # 2. Communication-aware A*
    # --------------------------------------------------------

    communication_path = (
        communication_astar_search(
            grid_map=grid_map,
            start=request.start,
            goal=request.goal,
            radio_map=RADIO_MAP,
            altitude_m=request.altitude_m,
            resolution_m=GRID_RESOLUTION_M,
            communication_weight=(
                request.communication_weight
            ),
        )
    )

    communication_metrics = (
        evaluate_grid_path(
            path=communication_path,
            start=request.start,
            radio_map=RADIO_MAP,
            altitude_m=request.altitude_m,
            resolution_m=GRID_RESOLUTION_M,
            radio_origin=radio_origin,
        )
    )

    # --------------------------------------------------------
    # 3. Structured comparison result
    # --------------------------------------------------------

    normal_result = RouteOptionMetrics(
        planner="normal",
        raw_path=normal_path,
        path_nodes=normal_metrics[
            "path_nodes"
        ],
        planned_distance_m=normal_metrics[
            "path_distance_m"
        ],
        mean_coverage_score=normal_metrics[
            "mean_coverage_score"
        ],
        min_coverage_score=normal_metrics[
            "min_coverage_score"
        ],
        mean_rsrp_dbm=normal_metrics[
            "mean_rsrp_dbm"
        ],
        min_rsrp_dbm=normal_metrics[
            "min_rsrp_dbm"
        ],
        mean_sinr_db=normal_metrics[
            "mean_sinr_db"
        ],
        min_sinr_db=normal_metrics[
            "min_sinr_db"
        ],
        handover_count=normal_metrics[
            "handover_count"
        ],
    )

    communication_result = (
        RouteOptionMetrics(
            planner="communication_aware",
            raw_path=communication_path,
            path_nodes=communication_metrics[
                "path_nodes"
            ],
            planned_distance_m=(
                communication_metrics[
                    "path_distance_m"
                ]
            ),
            mean_coverage_score=(
                communication_metrics[
                    "mean_coverage_score"
                ]
            ),
            min_coverage_score=(
                communication_metrics[
                    "min_coverage_score"
                ]
            ),
            mean_rsrp_dbm=(
                communication_metrics[
                    "mean_rsrp_dbm"
                ]
            ),
            min_rsrp_dbm=(
                communication_metrics[
                    "min_rsrp_dbm"
                ]
            ),
            mean_sinr_db=(
                communication_metrics[
                    "mean_sinr_db"
                ]
            ),
            min_sinr_db=(
                communication_metrics[
                    "min_sinr_db"
                ]
            ),
            handover_count=(
                communication_metrics[
                    "handover_count"
                ]
            ),
        )
    )

    return MissionCompareResponse(
        start=request.start,
        goal=request.goal,
        altitude_m=request.altitude_m,
        communication_weight=(
            request.communication_weight
        ),
        normal=normal_result,
        communication_aware=(
            communication_result
        ),
    )
