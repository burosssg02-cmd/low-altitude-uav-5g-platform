import unittest

from planner.astar import (
    PathNotFoundError,
    astar_search,
)
from planner.grid_map import GridMap


class TestAStar(unittest.TestCase):

    def test_path_around_obstacle(self):

        obstacles = {
            (4, 1),
            (4, 2),
            (4, 3),
            (4, 4),
            (4, 5),
            (4, 6),
        }

        grid_map = GridMap(
            width=10,
            height=8,
            obstacles=obstacles,
        )

        start = (1, 3)
        goal = (8, 3)

        path = astar_search(
            grid_map,
            start,
            goal,
        )

        self.assertEqual(path[0], start)
        self.assertEqual(path[-1], goal)

        for node in path:
            self.assertTrue(
                grid_map.is_free(node)
            )

        print("\nA* path:")
        print(path)

        print("\nGrid:")
        print(
            grid_map.render(
                start=start,
                goal=goal,
                path=path,
            )
        )

        print(
            f"\nPath nodes: {len(path)}"
        )

    def test_blocked_start(self):

        grid_map = GridMap(
            width=5,
            height=5,
            obstacles={(0, 0)},
        )

        with self.assertRaises(ValueError):
            astar_search(
                grid_map,
                (0, 0),
                (4, 4),
            )

    def test_no_path(self):

        obstacles = {
            (2, 0),
            (2, 1),
            (2, 2),
            (2, 3),
            (2, 4),
        }

        grid_map = GridMap(
            width=5,
            height=5,
            obstacles=obstacles,
        )

        with self.assertRaises(PathNotFoundError):
            astar_search(
                grid_map,
                (0, 2),
                (4, 2),
            )


if __name__ == "__main__":
    unittest.main()
