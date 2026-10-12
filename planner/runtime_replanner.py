import math
from dataclasses import (
    asdict,
    dataclass,
)

from communication.radio_map import (
    RadioMap,
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
    GridNode,
)


@dataclass
class RuntimeWaypoint:
    grid_node: GridNode
    east_m: float
    north_m: float
    altitude_m: float


@dataclass
class RuntimeReplanProposal:
    current_grid: GridNode
    goal: GridNode
    radio_origin: GridNode

    raw_path: list[GridNode]

    waypoints: list[RuntimeWaypoint]

    metrics: dict

    def to_dict(self) -> dict:
        return asdict(self)


def validate_replan_proposal(
    proposal: RuntimeReplanProposal,
    grid_map: GridMap,
) -> None:
    """
    Deterministic safety validation before a
    runtime route is allowed to reach PX4.

    This validator checks the planner-level
    structural safety constraints only.
    """

    path = proposal.raw_path

    if not path:
        raise ValueError(
            "Replan path must not be empty"
        )

    if path[0] != proposal.current_grid:
        raise ValueError(
            "Replan path must start from "
            "current_grid"
        )

    if path[-1] != proposal.goal:
        raise ValueError(
            "Replan path must end at goal"
        )

    if len(path) != len(
        proposal.waypoints
    ):
        raise ValueError(
            "Path and waypoint counts differ"
        )

    for index, node in enumerate(path):
        if not grid_map.is_free(node):
            raise ValueError(
                f"Blocked or invalid node: {node}"
            )

        waypoint = (
            proposal.waypoints[index]
        )

        if waypoint.grid_node != node:
            raise ValueError(
                "Waypoint grid node mismatch"
            )

        values = (
            waypoint.east_m,
            waypoint.north_m,
            waypoint.altitude_m,
        )

        if not all(
            math.isfinite(value)
            for value in values
        ):
            raise ValueError(
                "Waypoint contains "
                "non-finite coordinates"
            )

        if waypoint.altitude_m <= 0:
            raise ValueError(
                "Waypoint altitude must "
                "be positive"
            )

    for first, second in zip(
        path,
        path[1:],
    ):
        dx = abs(
            second[0] - first[0]
        )

        dy = abs(
            second[1] - first[1]
        )

        if dx + dy != 1:
            raise ValueError(
                "Replan path contains "
                "non-adjacent grid nodes"
            )


def build_runtime_replan(
    *,
    grid_map: GridMap,
    radio_map: RadioMap,
    current_grid: GridNode,
    goal: GridNode,
    radio_origin: GridNode,
    altitude_m: float = 5.0,
    resolution_m: float = 5.0,
    communication_weight: float = 2.0,
) -> RuntimeReplanProposal:
    """
    Build a communication-aware remaining route.

    Important coordinate rule:

    current_grid:
        A* search starts here.

    radio_origin:
        Radio Map and local EN coordinates remain
        referenced to the ORIGINAL mission start.

    Therefore a mid-flight replan never resets the
    coordinate system to E=0, N=0.
    """

    if altitude_m <= 0:
        raise ValueError(
            "altitude_m must be positive"
        )

    if resolution_m <= 0:
        raise ValueError(
            "resolution_m must be positive"
        )

    path = communication_astar_search(
        grid_map=grid_map,
        start=current_grid,
        goal=goal,
        radio_map=radio_map,
        altitude_m=altitude_m,
        resolution_m=resolution_m,
        communication_weight=(
            communication_weight
        ),
        radio_origin=radio_origin,
    )

    metrics = evaluate_grid_path(
        path=path,
        start=current_grid,
        radio_map=radio_map,
        altitude_m=altitude_m,
        resolution_m=resolution_m,
        radio_origin=radio_origin,
    )

    waypoints = []

    for node in path:
        east_m, north_m = (
            grid_to_local(
                node=node,
                origin_node=radio_origin,
                resolution_m=resolution_m,
            )
        )

        waypoints.append(
            RuntimeWaypoint(
                grid_node=node,
                east_m=east_m,
                north_m=north_m,
                altitude_m=altitude_m,
            )
        )

    proposal = RuntimeReplanProposal(
        current_grid=current_grid,
        goal=goal,
        radio_origin=radio_origin,
        raw_path=path,
        waypoints=waypoints,
        metrics=metrics,
    )

    validate_replan_proposal(
        proposal=proposal,
        grid_map=grid_map,
    )

    return proposal
