import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("TkAgg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle


GRID_RESOLUTION_M = 5.0
START_GRID = (1, 3)

# 当前 V0.2 测试地图中的障碍物
OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


def find_latest_run():
    """
    Find the latest mission run that contains
    planned waypoints, actual trajectory, and summary.
    """

    runs_dir = Path("outputs/runs")

    if not runs_dir.exists():
        raise FileNotFoundError(
            "outputs/runs does not exist"
        )

    valid_runs = []

    for run_dir in runs_dir.iterdir():

        if not run_dir.is_dir():
            continue

        required_files = [
            run_dir / "planned_waypoints.csv",
            run_dir / "actual_trajectory.csv",
            run_dir / "mission_summary.json",
        ]

        if all(path.exists() for path in required_files):
            valid_runs.append(run_dir)

    if not valid_runs:
        raise FileNotFoundError(
            "No complete mission run found"
        )

    return max(
        valid_runs,
        key=lambda path: path.stat().st_mtime,
    )


def load_planned_waypoints(csv_path):
    waypoints = []

    with open(
        csv_path,
        "r",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            waypoints.append(
                {
                    "waypoint_id":
                        row["waypoint_id"],

                    "east_m":
                        float(row["east_m"]),

                    "north_m":
                        float(row["north_m"]),
                }
            )

    return waypoints


def load_actual_trajectory(csv_path):
    trajectory = []

    with open(
        csv_path,
        "r",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(file)

        for row in reader:
            trajectory.append(
                {
                    "east_m":
                        float(row["east_m"]),

                    "north_m":
                        float(row["north_m"]),

                    "relative_altitude_m":
                        float(row["relative_altitude_m"]),

                    "target_waypoint":
                        row["target_waypoint"],
                }
            )

    return trajectory


def load_summary(json_path):
    with open(
        json_path,
        "r",
        encoding="utf-8",
    ) as file:
        return json.load(file)


def grid_to_local(
    grid_x,
    grid_y,
):
    """
    Convert obstacle grid coordinates into
    the same East/North system used by the UAV.
    """

    dx = grid_x - START_GRID[0]
    dy = grid_y - START_GRID[1]

    east_m = (
        dx * GRID_RESOLUTION_M
    )

    north_m = (
        -dy * GRID_RESOLUTION_M
    )

    return east_m, north_m


def draw_obstacles(ax):
    """
    Draw grid obstacle cells as square regions.
    """

    half_cell = (
        GRID_RESOLUTION_M / 2.0
    )

    for grid_x, grid_y in OBSTACLES:

        east_m, north_m = grid_to_local(
            grid_x,
            grid_y,
        )

        rectangle = Rectangle(
            (
                east_m - half_cell,
                north_m - half_cell,
            ),
            GRID_RESOLUTION_M,
            GRID_RESOLUTION_M,
            alpha=0.35,
        )

        ax.add_patch(rectangle)


def main():

    # =====================================================
    # 1. Find latest complete mission
    # =====================================================

    run_dir = find_latest_run()

    print(
        f"[RUN] Using: {run_dir}"
    )

    planned_csv = (
        run_dir
        / "planned_waypoints.csv"
    )

    actual_csv = (
        run_dir
        / "actual_trajectory.csv"
    )

    summary_json = (
        run_dir
        / "mission_summary.json"
    )

    output_png = (
        run_dir
        / "trajectory_comparison.png"
    )

    # =====================================================
    # 2. Load data
    # =====================================================

    planned = load_planned_waypoints(
        planned_csv
    )

    actual = load_actual_trajectory(
        actual_csv
    )

    summary = load_summary(
        summary_json
    )

    if not planned:
        raise ValueError(
            "planned_waypoints.csv is empty"
        )

    if not actual:
        raise ValueError(
            "actual_trajectory.csv is empty"
        )

    # =====================================================
    # 3. Prepare coordinates
    # =====================================================

    planned_east = [
        point["east_m"]
        for point in planned
    ]

    planned_north = [
        point["north_m"]
        for point in planned
    ]

    actual_east = [
        point["east_m"]
        for point in actual
    ]

    actual_north = [
        point["north_m"]
        for point in actual
    ]

    # =====================================================
    # 4. Create figure
    # =====================================================

    fig, ax = plt.subplots(
        figsize=(10, 7)
    )

    # Obstacles
    draw_obstacles(ax)

    # Planned route
    ax.plot(
        planned_east,
        planned_north,
        marker="o",
        linestyle="--",
        linewidth=2,
        label="Planned A* Path",
    )

    # Actual PX4 trajectory
    ax.plot(
        actual_east,
        actual_north,
        linewidth=2,
        label="Actual PX4 Trajectory",
    )

    # Start
    ax.scatter(
        planned_east[0],
        planned_north[0],
        marker="^",
        s=160,
        label="Start",
        zorder=5,
    )

    # Goal
    ax.scatter(
        planned_east[-1],
        planned_north[-1],
        marker="*",
        s=220,
        label="Goal",
        zorder=5,
    )

    # =====================================================
    # 5. Label waypoints
    # =====================================================

    for waypoint in planned:

        ax.annotate(
            waypoint["waypoint_id"],
            (
                waypoint["east_m"],
                waypoint["north_m"],
            ),
            xytext=(6, 6),
            textcoords="offset points",
        )

    # =====================================================
    # 6. Metrics text
    # =====================================================

    metrics_text = (
        f"Planned distance: "
        f"{summary['planned_distance_m']:.2f} m\n"
        f"Actual distance: "
        f"{summary['actual_distance_m']:.2f} m\n"
        f"Mission time: "
        f"{summary['mission_duration_s']:.2f} s\n"
        f"Mean WP error: "
        f"{summary['mean_waypoint_error_m']:.3f} m\n"
        f"Max WP error: "
        f"{summary['max_waypoint_error_m']:.3f} m\n"
        f"Mean path deviation: "
        f"{summary['mean_path_deviation_m']:.3f} m\n"
        f"Max path deviation: "
        f"{summary['max_path_deviation_m']:.3f} m\n"
        f"Flight efficiency: "
        f"{summary['flight_efficiency'] * 100:.2f}%"
    )

    ax.text(
        0.98,
        0.98,
        metrics_text,
        transform=ax.transAxes,
        verticalalignment="top",
        horizontalalignment="right",
        bbox={
            "boxstyle": "round",
            "alpha": 0.8,
        },
    )

    # =====================================================
    # 7. Figure style
    # =====================================================

    ax.set_title(
        "Planned A* Path vs Actual PX4 Trajectory"
    )

    ax.set_xlabel(
        "East (m)"
    )

    ax.set_ylabel(
        "North (m)"
    )

    ax.grid(
        True,
        alpha=0.3,
    )

    ax.axis(
        "equal"
    )

    ax.legend(
        loc="best"
    )

    fig.tight_layout()

    # =====================================================
    # 8. Save and display
    # =====================================================

    fig.savefig(
        output_png,
        dpi=200,
    )

    print(
        f"[OK] Figure saved: "
        f"{output_png}"
    )

    plt.show()


if __name__ == "__main__":
    main()
