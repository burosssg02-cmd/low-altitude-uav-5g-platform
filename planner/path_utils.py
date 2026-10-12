from planner.grid_map import GridNode


def _direction(
    node_a: GridNode,
    node_b: GridNode,
) -> tuple[int, int]:
    """
    Return movement direction from node_a to node_b.
    """

    return (
        node_b[0] - node_a[0],
        node_b[1] - node_a[1],
    )


def simplify_path(
    path: list[GridNode],
) -> list[GridNode]:
    """
    Simplify an A* grid path by retaining only:
        - start
        - turning points
        - goal

    Example:
        [(1,3), (2,3), (3,3), (3,2), (3,1)]

    becomes:
        [(1,3), (3,3), (3,1)]
    """

    if len(path) <= 2:
        return path.copy()

    simplified = [path[0]]

    previous_direction = _direction(
        path[0],
        path[1],
    )

    for index in range(1, len(path) - 1):

        current_direction = _direction(
            path[index],
            path[index + 1],
        )

        if current_direction != previous_direction:
            simplified.append(path[index])

        previous_direction = current_direction

    simplified.append(path[-1])

    return simplified
