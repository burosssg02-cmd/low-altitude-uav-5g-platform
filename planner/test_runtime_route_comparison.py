import pytest

from communication.radio_map import (
    build_demo_radio_map,
)

from planner.grid_map import (
    GridMap,
)

from planner.runtime_route_comparison import (
    compare_runtime_routes,
)


OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


def make_grid():
    return GridMap(
        width=10,
        height=8,
        obstacles=OBSTACLES,
    )


def test_real_runtime_comparison():
    result = compare_runtime_routes(
        grid_map=make_grid(),

        start=(5, 0),
        goal=(8, 3),

        # Radio coordinates still use
        # the original mission origin.
        radio_origin=(1, 3),

        radio_map=(
            build_demo_radio_map()
        ),

        altitude_m=5.0,
        resolution_m=5.0,
        communication_weight=2.0,
    )

    normal = result[
        "normal"
    ]

    communication = result[
        "communication_aware"
    ]

    assert (
        normal["raw_path"]
        == [
            (5, 0),
            (6, 0),
            (7, 0),
            (8, 0),
            (8, 1),
            (8, 2),
            (8, 3),
        ]
    )

    assert (
        communication["raw_path"]
        == [
            (5, 0),
            (5, 1),
            (5, 2),
            (5, 3),
            (6, 3),
            (7, 3),
            (8, 3),
        ]
    )

    assert (
        normal[
            "planned_distance_m"
        ]
        == pytest.approx(30.0)
    )

    assert (
        communication[
            "planned_distance_m"
        ]
        == pytest.approx(30.0)
    )

    assert (
        communication[
            "mean_coverage_score"
        ]
        > normal[
            "mean_coverage_score"
        ]
    )

    assert (
        communication[
            "mean_rsrp_dbm"
        ]
        > normal[
            "mean_rsrp_dbm"
        ]
    )

    assert (
        communication[
            "handover_count"
        ]
        < normal[
            "handover_count"
        ]
    )


def test_runtime_radio_origin_is_preserved():
    result = compare_runtime_routes(
        grid_map=make_grid(),
        start=(5, 0),
        goal=(8, 3),
        radio_origin=(1, 3),
        radio_map=(
            build_demo_radio_map()
        ),
        altitude_m=5.0,
        resolution_m=5.0,
        communication_weight=2.0,
    )

    assert (
        result["radio_origin"]
        == (1, 3)
    )

    assert (
        result["normal"]
        ["mean_rsrp_dbm"]
        < -90.0
    )
