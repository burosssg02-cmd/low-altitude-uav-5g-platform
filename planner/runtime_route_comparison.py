from communication.radio_map import (
    RadioMap,
)

from planner.astar import (
    astar_search,
)

from planner.communication_astar import (
    communication_astar_search,
    query_node_radio,
)

from planner.grid_map import (
    GridMap,
    GridNode,
)


def evaluate_runtime_path(
    *,
    path: list[GridNode],
    start: GridNode,
    radio_origin: GridNode,
    radio_map: RadioMap,
    altitude_m: float,
    resolution_m: float,
) -> dict:
    """
    Evaluate one remaining runtime path.

    Important:
    - path search starts from current UAV grid node;
    - radio coordinates remain referenced to the
      original mission start.
    """

    if not path:
        raise ValueError(
            "Runtime path must not be empty"
        )

    samples = []

    for node in path:
        sample = query_node_radio(
            node=node,
            start=start,
            radio_origin=radio_origin,
            radio_map=radio_map,
            altitude_m=altitude_m,
            resolution_m=resolution_m,
        )

        samples.append(
            sample
        )

    scores = [
        float(
            item["coverage_score"]
        )
        for item in samples
    ]

    rsrp_values = [
        float(
            item["rsrp_dbm"]
        )
        for item in samples
    ]

    sinr_values = [
        float(
            item["sinr_db"]
        )
        for item in samples
    ]

    serving_bs = [
        item["serving_bs"]
        for item in samples
    ]

    handover_count = sum(
        1
        for index in range(
            1,
            len(serving_bs),
        )
        if (
            serving_bs[index]
            != serving_bs[index - 1]
        )
    )

    return {
        "path_nodes":
            len(path),

        "planned_distance_m":
            max(
                len(path) - 1,
                0,
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


def compare_runtime_routes(
    *,
    grid_map: GridMap,
    start: GridNode,
    goal: GridNode,
    radio_origin: GridNode,
    radio_map: RadioMap,
    altitude_m: float,
    resolution_m: float,
    communication_weight: float,
) -> dict:
    """
    Pure deterministic comparison used by the
    flight-time incident handler.

    No HTTP.
    No LLM.
    No external network.
    """

    normal_path = astar_search(
        grid_map,
        start,
        goal,
    )

    communication_path = (
        communication_astar_search(
            grid_map=grid_map,
            start=start,
            goal=goal,
            radio_map=radio_map,
            altitude_m=altitude_m,
            resolution_m=(
                resolution_m
            ),
            communication_weight=(
                communication_weight
            ),
            radio_origin=(
                radio_origin
            ),
        )
    )

    normal_metrics = (
        evaluate_runtime_path(
            path=normal_path,
            start=start,
            radio_origin=(
                radio_origin
            ),
            radio_map=radio_map,
            altitude_m=altitude_m,
            resolution_m=(
                resolution_m
            ),
        )
    )

    communication_metrics = (
        evaluate_runtime_path(
            path=communication_path,
            start=start,
            radio_origin=(
                radio_origin
            ),
            radio_map=radio_map,
            altitude_m=altitude_m,
            resolution_m=(
                resolution_m
            ),
        )
    )

    return {
        "start":
            start,

        "goal":
            goal,

        "radio_origin":
            radio_origin,

        "normal": {
            "planner":
                "normal",

            "raw_path":
                normal_path,

            **normal_metrics,
        },

        "communication_aware": {
            "planner":
                "communication_aware",

            "raw_path":
                communication_path,

            **communication_metrics,
        },
    }
