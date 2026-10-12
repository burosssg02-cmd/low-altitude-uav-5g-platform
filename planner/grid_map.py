from typing import Iterable

GridNode = tuple[int, int]


class GridMap:
    """
    2D occupancy grid.

    Coordinate convention:
        x -> horizontal direction
        y -> vertical direction

    Cell value:
        free      -> flyable
        obstacle  -> no-fly / blocked
    """

    def __init__(
        self,
        width: int,
        height: int,
        obstacles: Iterable[GridNode] | None = None,
    ):
        if width <= 0 or height <= 0:
            raise ValueError("width and height must be positive")

        self.width = width
        self.height = height
        self.obstacles = set(obstacles or [])

    def in_bounds(self, node: GridNode) -> bool:
        x, y = node

        return (
            0 <= x < self.width
            and 0 <= y < self.height
        )

    def is_free(self, node: GridNode) -> bool:
        return (
            self.in_bounds(node)
            and node not in self.obstacles
        )

    def neighbors(self, node: GridNode) -> list[GridNode]:
        """
        4-connected grid:
            up / down / left / right
        """
        x, y = node

        candidates = [
            (x + 1, y),
            (x - 1, y),
            (x, y + 1),
            (x, y - 1),
        ]

        return [
            candidate
            for candidate in candidates
            if self.is_free(candidate)
        ]

    def render(
        self,
        start: GridNode | None = None,
        goal: GridNode | None = None,
        path: list[GridNode] | None = None,
    ) -> str:
        path_set = set(path or [])

        rows = []

        for y in range(self.height):
            row = []

            for x in range(self.width):
                node = (x, y)

                if node == start:
                    symbol = "S"
                elif node == goal:
                    symbol = "G"
                elif node in self.obstacles:
                    symbol = "#"
                elif node in path_set:
                    symbol = "*"
                else:
                    symbol = "."

                row.append(symbol)

            rows.append(" ".join(row))

        return "\n".join(rows)
