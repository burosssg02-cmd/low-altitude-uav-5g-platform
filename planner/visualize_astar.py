import matplotlib

matplotlib.use("TkAgg")

import matplotlib.pyplot as plt

from planner.astar import astar_search
from planner.grid_map import GridMap
from planner.path_utils import simplify_path


def main():
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

    raw_path = astar_search(
        grid_map,
        start,
        goal,
    )

    simplified_path = simplify_path(raw_path)

    print("Raw path:")
    print(raw_path)

    print("\nSimplified path:")
    print(simplified_path)

    print(
        f"\nNodes: {len(raw_path)} -> "
        f"{len(simplified_path)}"
    )

    # -------------------------
    # Obstacles
    # -------------------------
    if obstacles:
        obstacle_x = [
            node[0]
            for node in obstacles
        ]

        obstacle_y = [
            node[1]
            for node in obstacles
        ]

        plt.scatter(
            obstacle_x,
            obstacle_y,
            marker="s",
            s=300,
            label="Obstacle",
        )

    # -------------------------
    # Raw A* path
    # -------------------------
    raw_x = [
        node[0]
        for node in raw_path
    ]

    raw_y = [
        node[1]
        for node in raw_path
    ]

    plt.plot(
        raw_x,
        raw_y,
        marker=".",
        linestyle="-",
        label="Raw A* Path",
    )

    # -------------------------
    # Simplified waypoints
    # -------------------------
    simplified_x = [
        node[0]
        for node in simplified_path
    ]

    simplified_y = [
        node[1]
        for node in simplified_path
    ]

    plt.plot(
        simplified_x,
        simplified_y,
        marker="o",
        linestyle="--",
        label="Simplified Waypoints",
    )

    # -------------------------
    # Start
    # -------------------------
    plt.scatter(
        start[0],
        start[1],
        marker="^",
        s=150,
        label="Start",
    )

    # -------------------------
    # Goal
    # -------------------------
    plt.scatter(
        goal[0],
        goal[1],
        marker="*",
        s=200,
        label="Goal",
    )

    plt.title(
        "A* UAV Path Planning"
    )

    plt.xlabel(
        "Grid X"
    )

    plt.ylabel(
        "Grid Y"
    )

    plt.xticks(
        range(grid_map.width)
    )

    plt.yticks(
        range(grid_map.height)
    )

    plt.grid(True)

    plt.axis(
        "equal"
    )

    # Make figure direction match the text grid
    plt.gca().invert_yaxis()

    plt.legend()

    plt.tight_layout()

    output_path = (
        "outputs/astar_path.png"
    )

    plt.savefig(
        output_path,
        dpi=200,
    )

    print(
        f"\n[OK] Figure saved to "
        f"{output_path}"
    )

    plt.show()


if __name__ == "__main__":
    main()
