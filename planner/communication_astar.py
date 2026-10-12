import heapq
import math

from communication.radio_map import RadioMap
from planner.astar import (
    PathNotFoundError,
    manhattan_distance,
    reconstruct_path,
)
from planner.coordinate_converter import (
    grid_to_local,
)
from planner.grid_map import (
    GridMap,
    GridNode,
)


def query_node_radio(
    node: GridNode,
    start: GridNode,
    radio_map: RadioMap,
    altitude_m: float,
    resolution_m: float,
    radio_origin: GridNode | None = None,
) -> dict:
    """
    Convert a grid node to local EN coordinates
    and query communication quality.
    """

    origin_node = (
        radio_origin
        if radio_origin is not None
        else start
    )

    east_m, north_m = grid_to_local(
        node=node,
        origin_node=origin_node,
        resolution_m=resolution_m,
    )

    return radio_map.query(
        east_m=east_m,
        north_m=north_m,
        altitude_m=altitude_m,
    )


def communication_astar_search(
    grid_map: GridMap,
    start: GridNode,
    goal: GridNode,
    radio_map: RadioMap,
    altitude_m: float = 5.0,
    resolution_m: float = 5.0,
    communication_weight: float = 2.0,
    radio_origin: GridNode | None = None,
) -> list[GridNode]:
    """
    Communication-aware A*.

    Cost:
        movement_cost
        +
        communication_weight
        * communication_risk

    communication_risk:
        1 - coverage_score
    """

    if communication_weight < 0:
        raise ValueError(
            "communication_weight must be non-negative"
        )

    if not grid_map.is_free(start):
        raise ValueError(
            f"Start node {start} is invalid or blocked"
        )

    if not grid_map.is_free(goal):
        raise ValueError(
            f"Goal node {goal} is invalid or blocked"
        )

    open_set: list[
        tuple[
            float,
            int,
            GridNode,
        ]
    ] = []

    counter = 0

    heapq.heappush(
        open_set,
        (
            manhattan_distance(
                start,
                goal,
            ),
            counter,
            start,
        ),
    )

    came_from: dict[
        GridNode,
        GridNode,
    ] = {}

    g_score: dict[
        GridNode,
        float,
    ] = {
        start: 0.0
    }

    closed_set: set[
        GridNode
    ] = set()

    while open_set:

        _, _, current = (
            heapq.heappop(
                open_set
            )
        )

        if current in closed_set:
            continue

        if current == goal:
            return reconstruct_path(
                came_from,
                current,
            )

        closed_set.add(
            current
        )

        for neighbor in (
            grid_map.neighbors(
                current
            )
        ):

            radio_result = (
                query_node_radio(
                    node=neighbor,
                    start=start,
                    radio_map=radio_map,
                    altitude_m=altitude_m,
                    resolution_m=resolution_m,
                    radio_origin=radio_origin,
                )
            )

            coverage_score = (
                radio_result[
                    "coverage_score"
                ]
            )

            communication_risk = (
                1.0
                - coverage_score
            )

            movement_cost = 1.0

            communication_cost = (
                communication_weight
                * communication_risk
            )

            step_cost = (
                movement_cost
                + communication_cost
            )

            tentative_g_score = (
                g_score[current]
                + step_cost
            )

            if (
                tentative_g_score
                >= g_score.get(
                    neighbor,
                    math.inf,
                )
            ):
                continue

            came_from[
                neighbor
            ] = current

            g_score[
                neighbor
            ] = (
                tentative_g_score
            )

            f_score = (
                tentative_g_score
                + manhattan_distance(
                    neighbor,
                    goal,
                )
            )

            counter += 1

            heapq.heappush(
                open_set,
                (
                    f_score,
                    counter,
                    neighbor,
                ),
            )

    raise PathNotFoundError(
        f"No path found from "
        f"{start} to {goal}"
    )


def evaluate_grid_path(
    path: list[GridNode],
    start: GridNode,
    radio_map: RadioMap,
    altitude_m: float = 5.0,
    resolution_m: float = 5.0,
    radio_origin: GridNode | None = None,
) -> dict:
    """
    Evaluate communication quality of
    a planned grid path.
    """

    if not path:
        raise ValueError(
            "Path must not be empty"
        )

    radio_results = []

    for node in path:

        radio_result = (
            query_node_radio(
                node=node,
                start=start,
                radio_map=radio_map,
                altitude_m=altitude_m,
                resolution_m=resolution_m,
                radio_origin=radio_origin,
            )
        )

        radio_results.append(
            radio_result
        )

    scores = [
        result[
            "coverage_score"
        ]
        for result
        in radio_results
    ]

    rsrp_values = [
        result[
            "rsrp_dbm"
        ]
        for result
        in radio_results
    ]

    sinr_values = [
        result[
            "sinr_db"
        ]
        for result
        in radio_results
    ]

    handover_count = 0
    previous_bs = None

    for result in radio_results:

        serving_bs = (
            result[
                "serving_bs"
            ]
        )

        if (
            previous_bs is not None
            and serving_bs
            != previous_bs
        ):
            handover_count += 1

        previous_bs = (
            serving_bs
        )

    return {
        "path_nodes":
            len(path),

        "path_distance_m":
            (
                len(path) - 1
            )
            * resolution_m,

        "mean_coverage_score":
            sum(scores)
            / len(scores),

        "min_coverage_score":
            min(scores),

        "mean_rsrp_dbm":
            sum(rsrp_values)
            / len(rsrp_values),

        "min_rsrp_dbm":
            min(rsrp_values),

        "mean_sinr_db":
            sum(sinr_values)
            / len(sinr_values),

        "min_sinr_db":
            min(sinr_values),

        "handover_count":
            handover_count,
    }
