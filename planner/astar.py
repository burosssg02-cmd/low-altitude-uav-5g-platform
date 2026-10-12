import heapq
import math

from planner.grid_map import GridMap, GridNode


class PathNotFoundError(Exception):
    pass


def manhattan_distance(
    node_a: GridNode,
    node_b: GridNode,
) -> float:
    """
    Manhattan heuristic for a 4-connected grid.
    """
    return abs(node_a[0] - node_b[0]) + abs(node_a[1] - node_b[1])


def reconstruct_path(
    came_from: dict[GridNode, GridNode],
    current: GridNode,
) -> list[GridNode]:
    path = [current]

    while current in came_from:
        current = came_from[current]
        path.append(current)

    path.reverse()

    return path


def astar_search(
    grid_map: GridMap,
    start: GridNode,
    goal: GridNode,
) -> list[GridNode]:

    if not grid_map.is_free(start):
        raise ValueError(f"Start node {start} is invalid or blocked")

    if not grid_map.is_free(goal):
        raise ValueError(f"Goal node {goal} is invalid or blocked")

    open_set: list[tuple[float, int, GridNode]] = []

    counter = 0

    heapq.heappush(
        open_set,
        (
            manhattan_distance(start, goal),
            counter,
            start,
        ),
    )

    came_from: dict[GridNode, GridNode] = {}

    g_score: dict[GridNode, float] = {
        start: 0.0
    }

    closed_set: set[GridNode] = set()

    while open_set:
        _, _, current = heapq.heappop(open_set)

        if current in closed_set:
            continue

        if current == goal:
            return reconstruct_path(
                came_from,
                current,
            )

        closed_set.add(current)

        for neighbor in grid_map.neighbors(current):

            tentative_g_score = (
                g_score[current] + 1.0
            )

            if tentative_g_score >= g_score.get(
                neighbor,
                math.inf,
            ):
                continue

            came_from[neighbor] = current

            g_score[neighbor] = tentative_g_score

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
        f"No path found from {start} to {goal}"
    )
