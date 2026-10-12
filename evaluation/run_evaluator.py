import json
from pathlib import Path

import matplotlib

# FastAPI background task must not open GUI windows.
matplotlib.use("Agg")

import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from evaluation.trajectory_metrics import (
    calculate_metrics,
    load_actual_trajectory,
    load_planned_waypoints,
)


GRID_RESOLUTION_M = 5.0

OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


def save_summary(
    metrics: dict,
    output_path: Path,
):
    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    with output_path.open(
        "w",
        encoding="utf-8",
    ) as file:
        json.dump(
            metrics,
            file,
            indent=2,
            ensure_ascii=False,
        )


def draw_obstacles(ax):
    """
    Draw the current virtual obstacle cells.

    Grid convention:
    x increases east,
    y increases south.
    """

    for grid_x, grid_y in OBSTACLES:
        east_m = (
            grid_x - 1
        ) * GRID_RESOLUTION_M

        north_m = (
            3 - grid_y
        ) * GRID_RESOLUTION_M

        rectangle = Rectangle(
            (
                east_m
                - GRID_RESOLUTION_M / 2,
                north_m
                - GRID_RESOLUTION_M / 2,
            ),
            GRID_RESOLUTION_M,
            GRID_RESOLUTION_M,
            alpha=0.35,
        )

        ax.add_patch(
            rectangle
        )


def generate_plot(
    planned,
    actual,
    metrics,
    output_path: Path,
):
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

    fig, ax = plt.subplots(
        figsize=(10, 7)
    )

    draw_obstacles(
        ax
    )

    ax.plot(
        planned_east,
        planned_north,
        marker="o",
        linestyle="--",
        linewidth=2,
        label="Planned A* Path",
    )

    ax.plot(
        actual_east,
        actual_north,
        linewidth=2,
        label="Actual PX4 Trajectory",
    )

    ax.scatter(
        planned_east[0],
        planned_north[0],
        marker="^",
        s=160,
        label="Start",
        zorder=5,
    )

    ax.scatter(
        planned_east[-1],
        planned_north[-1],
        marker="*",
        s=220,
        label="Goal",
        zorder=5,
    )

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

    metrics_text = (
        f"Planned distance: "
        f"{metrics['planned_distance_m']:.2f} m\n"
        f"Actual distance: "
        f"{metrics['actual_distance_m']:.2f} m\n"
        f"Duration: "
        f"{metrics['mission_duration_s']:.2f} s\n"
        f"Mean WP error: "
        f"{metrics['mean_waypoint_error_m']:.3f} m\n"
        f"Max WP error: "
        f"{metrics['max_waypoint_error_m']:.3f} m\n"
        f"Mean path deviation: "
        f"{metrics['mean_path_deviation_m']:.3f} m\n"
        f"Max path deviation: "
        f"{metrics['max_path_deviation_m']:.3f} m\n"
        f"Flight efficiency: "
        f"{metrics['flight_efficiency'] * 100:.2f}%"
    )

    ax.text(
        0.02,
        0.98,
        metrics_text,
        transform=ax.transAxes,
        verticalalignment="top",
        bbox={
            "boxstyle": "round",
            "alpha": 0.8,
        },
    )

    ax.set_xlabel(
        "East (m)"
    )

    ax.set_ylabel(
        "North (m)"
    )

    ax.set_title(
        "Planned A* Path vs Actual PX4 Trajectory"
    )

    ax.axis(
        "equal"
    )

    ax.grid(
        True
    )

    ax.legend()

    fig.tight_layout()

    fig.savefig(
        output_path,
        dpi=180,
    )

    plt.close(
        fig
    )


def evaluate_run(
    run_dir,
):
    run_dir = Path(
        run_dir
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

    comparison_png = (
        run_dir
        / "trajectory_comparison.png"
    )

    if not planned_csv.exists():
        raise FileNotFoundError(
            f"Missing: {planned_csv}"
        )

    if not actual_csv.exists():
        raise FileNotFoundError(
            f"Missing: {actual_csv}"
        )

    planned = load_planned_waypoints(
        planned_csv
    )

    actual = load_actual_trajectory(
        actual_csv
    )

    if not planned:
        raise ValueError(
            "Planned waypoint data is empty"
        )

    if not actual:
        raise ValueError(
            "Actual trajectory data is empty"
        )

    metrics = calculate_metrics(
        planned,
        actual,
    )

    save_summary(
        metrics,
        summary_json,
    )

    generate_plot(
        planned,
        actual,
        metrics,
        comparison_png,
    )

    print(
        f"[EVALUATION] Summary: "
        f"{summary_json}"
    )

    print(
        f"[EVALUATION] Plot: "
        f"{comparison_png}"
    )

    return metrics
