import unittest

from planner.path_utils import simplify_path


class TestPathUtils(unittest.TestCase):

    def test_simplify_path(self):

        raw_path = [
            (1, 3),
            (2, 3),
            (3, 3),
            (3, 2),
            (3, 1),
            (3, 0),
            (4, 0),
            (5, 0),
            (6, 0),
            (7, 0),
            (8, 0),
            (8, 1),
            (8, 2),
            (8, 3),
        ]

        simplified = simplify_path(raw_path)

        expected = [
            (1, 3),
            (3, 3),
            (3, 0),
            (8, 0),
            (8, 3),
        ]

        print("\nRaw path:")
        print(raw_path)

        print("\nSimplified path:")
        print(simplified)

        print(
            f"\nNodes: {len(raw_path)} -> {len(simplified)}"
        )

        self.assertEqual(
            simplified,
            expected,
        )

    def test_short_path(self):

        path = [
            (0, 0),
            (1, 0),
        ]

        self.assertEqual(
            simplify_path(path),
            path,
        )


if __name__ == "__main__":
    unittest.main()
