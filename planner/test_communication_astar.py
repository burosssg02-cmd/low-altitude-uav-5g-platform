import unittest

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

from planner.grid_map import (
    GridMap,
)


class TestCommunicationAStar(
    unittest.TestCase
):

    def setUp(self):

        self.obstacles = {
            (4, 1),
            (4, 2),
            (4, 3),
            (4, 4),
            (4, 5),
            (4, 6),
        }

        self.grid_map = GridMap(
            width=10,
            height=8,
            obstacles=self.obstacles,
        )

        self.start = (
            1,
            3,
        )

        self.goal = (
            8,
            3,
        )

        self.radio_map = (
            build_demo_radio_map()
        )


    def test_zero_weight_matches_astar(
        self,
    ):
        normal_path = astar_search(
            self.grid_map,
            self.start,
            self.goal,
        )

        communication_path = (
            communication_astar_search(
                grid_map=self.grid_map,
                start=self.start,
                goal=self.goal,
                radio_map=self.radio_map,
                altitude_m=5.0,
                resolution_m=5.0,
                communication_weight=0.0,
            )
        )

        self.assertEqual(
            normal_path,
            communication_path,
        )


    def test_communication_path_improves_coverage(
        self,
    ):
        normal_path = astar_search(
            self.grid_map,
            self.start,
            self.goal,
        )

        communication_path = (
            communication_astar_search(
                grid_map=self.grid_map,
                start=self.start,
                goal=self.goal,
                radio_map=self.radio_map,
                altitude_m=5.0,
                resolution_m=5.0,
                communication_weight=2.0,
            )
        )

        normal_metrics = (
            evaluate_grid_path(
                path=normal_path,
                start=self.start,
                radio_map=self.radio_map,
                altitude_m=5.0,
                resolution_m=5.0,
            )
        )

        communication_metrics = (
            evaluate_grid_path(
                path=communication_path,
                start=self.start,
                radio_map=self.radio_map,
                altitude_m=5.0,
                resolution_m=5.0,
            )
        )

        print(
            "\n=== Normal A* ==="
        )

        print(
            normal_path
        )

        print(
            normal_metrics
        )

        print(
            "\n=== Communication-Aware A* ==="
        )

        print(
            communication_path
        )

        print(
            communication_metrics
        )

        self.assertGreater(
            communication_metrics[
                "min_coverage_score"
            ],
            normal_metrics[
                "min_coverage_score"
            ],
        )

        self.assertGreater(
            communication_metrics[
                "mean_coverage_score"
            ],
            normal_metrics[
                "mean_coverage_score"
            ],
        )

        self.assertGreaterEqual(
            communication_metrics[
                "path_distance_m"
            ],
            normal_metrics[
                "path_distance_m"
            ],
        )

        # With the current demo Radio Map,
        # the communication-aware route should
        # prefer the lower corridor.
        self.assertTrue(
            any(
                y == 7
                for _, y
                in communication_path
            )
        )


if __name__ == "__main__":
    unittest.main()


def test_radio_origin_can_differ_from_search_start():
    from communication.radio_map import (
        build_demo_radio_map,
    )
    from planner.communication_astar import (
        query_node_radio,
    )

    radio_map = build_demo_radio_map()

    result = query_node_radio(
        node=(5, 0),
        start=(5, 0),
        radio_origin=(1, 3),
        radio_map=radio_map,
        altitude_m=5.0,
        resolution_m=5.0,
    )

    assert result["east_m"] == 20.0
    assert result["north_m"] == 15.0


def test_radio_origin_default_keeps_old_behavior():
    from communication.radio_map import (
        build_demo_radio_map,
    )
    from planner.communication_astar import (
        query_node_radio,
    )

    radio_map = build_demo_radio_map()

    result = query_node_radio(
        node=(5, 0),
        start=(5, 0),
        radio_map=radio_map,
        altitude_m=5.0,
        resolution_m=5.0,
    )

    assert result["east_m"] == 0.0
    assert result["north_m"] == 0.0
