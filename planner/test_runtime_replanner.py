import pytest

from communication.radio_map import (
    build_demo_radio_map,
)
from planner.grid_map import (
    GridMap,
)
from planner.runtime_replanner import (
    build_runtime_replan,
)


OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


def make_grid_map():
    return GridMap(
        width=10,
        height=8,
        obstacles=OBSTACLES,
    )


def test_runtime_replan_from_real_incident():
    proposal = build_runtime_replan(
        grid_map=make_grid_map(),
        radio_map=build_demo_radio_map(),

        current_grid=(5, 0),
        goal=(8, 3),

        radio_origin=(1, 3),

        altitude_m=5.0,
        resolution_m=5.0,
        communication_weight=2.0,
    )

    assert proposal.raw_path[0] == (
        5,
        0,
    )

    assert proposal.raw_path[-1] == (
        8,
        3,
    )

    assert (
        proposal.metrics[
            "path_distance_m"
        ]
        == 30.0
    )


def test_runtime_replan_keeps_global_frame():
    proposal = build_runtime_replan(
        grid_map=make_grid_map(),
        radio_map=build_demo_radio_map(),

        current_grid=(5, 0),
        goal=(8, 3),

        radio_origin=(1, 3),

        altitude_m=5.0,
        resolution_m=5.0,
        communication_weight=2.0,
    )

    first = proposal.waypoints[0]

    # (5,0) relative to original mission
    # origin (1,3) must be E=20,N=15.
    assert first.east_m == 20.0
    assert first.north_m == 15.0

    # It must NOT reset current position
    # to local (0,0).
    assert (
        first.east_m,
        first.north_m,
    ) != (
        0.0,
        0.0,
    )


def test_runtime_replan_goal_coordinates():
    proposal = build_runtime_replan(
        grid_map=make_grid_map(),
        radio_map=build_demo_radio_map(),

        current_grid=(5, 0),
        goal=(8, 3),

        radio_origin=(1, 3),

        altitude_m=5.0,
        resolution_m=5.0,
        communication_weight=2.0,
    )

    last = proposal.waypoints[-1]

    assert last.grid_node == (
        8,
        3,
    )

    assert last.east_m == 35.0

    assert last.north_m == 0.0

    assert last.altitude_m == 5.0
