import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Rectangle

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

from planner.coordinate_converter import (
    grid_to_local,
)

from planner.grid_map import (
    GridMap,
)


# ============================================================
# Configuration
# ============================================================

GRID_WIDTH = 10
GRID_HEIGHT = 8

GRID_RESOLUTION_M = 5.0

START = (1, 3)
GOAL = (8, 3)

ALTITUDE_M = 5.0

COMMUNICATION_WEIGHT = 2.0


OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


OUTPUT_DIR = Path(
    "outputs/communication_planner"
)


# ============================================================
# Coordinate helpers
# ============================================================

def path_to_local(
    path,
):
    coordinates = []

    for node in path:

        east_m, north_m = grid_to_local(
            node=node,
            origin_node=START,
            resolution_m=GRID_RESOLUTION_M,
        )

        coordinates.append(
            (
                east_m,
                north_m,
            )
        )

    return coordinates


# ============================================================
# Radio Map heatmap
# ============================================================

def build_coverage_grid(
    radio_map,
):
    """
    Build a dense Coverage Score map covering
    the current planner area.
    """

    east_values = np.arange(
        -7.5,
        42.5 + 1.0,
        1.0,
    )

    north_values = np.arange(
        -22.5,
        17.5 + 1.0,
        1.0,
    )

    score_grid = np.zeros(
        (
            len(north_values),
            len(east_values),
        )
    )

    for north_index, north_m in enumerate(
        north_values
    ):

        for east_index, east_m in enumerate(
            east_values
        ):

            result = radio_map.query(
                east_m=float(east_m),
                north_m=float(north_m),
                altitude_m=ALTITUDE_M,
            )

            score_grid[
                north_index,
                east_index,
            ] = result[
                "coverage_score"
            ]

    return (
        east_values,
        north_values,
        score_grid,
    )


# ============================================================
# Obstacle drawing
# ============================================================

def draw_obstacles(
    ax,
):
    first = True

    for obstacle in OBSTACLES:

        east_m, north_m = grid_to_local(
            node=obstacle,
            origin_node=START,
            resolution_m=GRID_RESOLUTION_M,
        )

        rectangle = Rectangle(
            (
                east_m
                - GRID_RESOLUTION_M / 2,
                north_m
                - GRID_RESOLUTION_M / 2,
            ),
            GRID_RESOLUTION_M,
            GRID_RESOLUTION_M,
            alpha=0.65,
            label=(
                "Obstacle"
                if first
                else None
            ),
        )

        first = False

        ax.add_patch(
            rectangle
        )


# ============================================================
# Metrics helpers
# ============================================================

def build_comparison(
    normal_metrics,
    communication_metrics,
):
    distance_change_m = (
        communication_metrics[
            "path_distance_m"
        ]
        - normal_metrics[
            "path_distance_m"
        ]
    )

    distance_change_pct = (
        distance_change_m
        / normal_metrics[
            "path_distance_m"
        ]
        * 100.0
    )

    mean_score_gain = (
        communication_metrics[
            "mean_coverage_score"
        ]
        - normal_metrics[
            "mean_coverage_score"
        ]
    )

    min_score_gain = (
        communication_metrics[
            "min_coverage_score"
        ]
        - normal_metrics[
            "min_coverage_score"
        ]
    )

    mean_rsrp_gain_db = (
        communication_metrics[
            "mean_rsrp_dbm"
        ]
        - normal_metrics[
            "mean_rsrp_dbm"
        ]
    )

    min_rsrp_gain_db = (
        communication_metrics[
            "min_rsrp_dbm"
        ]
        - normal_metrics[
            "min_rsrp_dbm"
        ]
    )

    mean_sinr_gain_db = (
        communication_metrics[
            "mean_sinr_db"
        ]
        - normal_metrics[
            "mean_sinr_db"
        ]
    )

    min_sinr_gain_db = (
        communication_metrics[
            "min_sinr_db"
        ]
        - normal_metrics[
            "min_sinr_db"
        ]
    )

    return {
        "distance_change_m":
            distance_change_m,

        "distance_change_pct":
            distance_change_pct,

        "mean_coverage_score_gain":
            mean_score_gain,

        "min_coverage_score_gain":
            min_score_gain,

        "mean_rsrp_gain_db":
            mean_rsrp_gain_db,

        "min_rsrp_gain_db":
            min_rsrp_gain_db,

        "mean_sinr_gain_db":
            mean_sinr_gain_db,

        "min_sinr_gain_db":
            min_sinr_gain_db,

        "handover_reduction":
            (
                normal_metrics[
                    "handover_count"
                ]
                - communication_metrics[
                    "handover_count"
                ]
            ),
    }


# ============================================================
# Main
# ============================================================

def main():

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # --------------------------------------------------------
    # 1. Build environment
    # --------------------------------------------------------

    grid_map = GridMap(
        width=GRID_WIDTH,
        height=GRID_HEIGHT,
        obstacles=OBSTACLES,
    )

    radio_map = (
        build_demo_radio_map()
    )

    # --------------------------------------------------------
    # 2. Normal A*
    # --------------------------------------------------------

    normal_path = astar_search(
        grid_map,
        START,
        GOAL,
    )

    normal_metrics = (
        evaluate_grid_path(
            path=normal_path,
            start=START,
            radio_map=radio_map,
            altitude_m=ALTITUDE_M,
            resolution_m=GRID_RESOLUTION_M,
        )
    )

    # --------------------------------------------------------
    # 3. Communication-aware A*
    # --------------------------------------------------------

    communication_path = (
        communication_astar_search(
            grid_map=grid_map,
            start=START,
            goal=GOAL,
            radio_map=radio_map,
            altitude_m=ALTITUDE_M,
            resolution_m=GRID_RESOLUTION_M,
            communication_weight=(
                COMMUNICATION_WEIGHT
            ),
        )
    )

    communication_metrics = (
        evaluate_grid_path(
            path=communication_path,
            start=START,
            radio_map=radio_map,
            altitude_m=ALTITUDE_M,
            resolution_m=GRID_RESOLUTION_M,
        )
    )

    comparison = build_comparison(
        normal_metrics,
        communication_metrics,
    )

    # --------------------------------------------------------
    # 4. Save JSON results
    # --------------------------------------------------------

    output_json = (
        OUTPUT_DIR
        / "planner_comparison.json"
    )

    result = {
        "configuration": {
            "altitude_m":
                ALTITUDE_M,

            "grid_resolution_m":
                GRID_RESOLUTION_M,

            "communication_weight":
                COMMUNICATION_WEIGHT,
        },

        "normal_astar": {
            "path":
                normal_path,

            "metrics":
                normal_metrics,
        },

        "communication_aware_astar": {
            "path":
                communication_path,

            "metrics":
                communication_metrics,
        },

        "comparison":
            comparison,
    }

    with output_json.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            result,
            file,
            indent=2,
            ensure_ascii=False,
        )

    # --------------------------------------------------------
    # 5. Build Radio Map background
    # --------------------------------------------------------

    (
        east_values,
        north_values,
        score_grid,
    ) = build_coverage_grid(
        radio_map
    )

    normal_local = (
        path_to_local(
            normal_path
        )
    )

    communication_local = (
        path_to_local(
            communication_path
        )
    )

    normal_east = [
        point[0]
        for point
        in normal_local
    ]

    normal_north = [
        point[1]
        for point
        in normal_local
    ]

    communication_east = [
        point[0]
        for point
        in communication_local
    ]

    communication_north = [
        point[1]
        for point
        in communication_local
    ]

    # --------------------------------------------------------
    # 6. Plot
    # --------------------------------------------------------

    fig, ax = plt.subplots(
        figsize=(12, 8)
    )

    image = ax.imshow(
        score_grid,
        origin="lower",
        extent=[
            east_values[0],
            east_values[-1],
            north_values[0],
            north_values[-1],
        ],
        aspect="auto",
        vmin=0.0,
        vmax=1.0,
    )

    colorbar = fig.colorbar(
        image,
        ax=ax,
    )

    colorbar.set_label(
        "5G Coverage Score"
    )

    # Obstacles
    draw_obstacles(
        ax
    )

    # Weak coverage zone
    weak_zone = Rectangle(
        (
            20.0,
            5.0,
        ),
        15.0,
        15.0,
        fill=False,
        linewidth=2,
        linestyle=":",
        label="Weak Coverage Zone",
    )

    ax.add_patch(
        weak_zone
    )

    # Normal A*
    ax.plot(
        normal_east,
        normal_north,
        marker="o",
        linestyle="--",
        linewidth=2.2,
        label="Normal A*",
    )

    # Communication-aware A*
    ax.plot(
        communication_east,
        communication_north,
        marker="s",
        linestyle="-",
        linewidth=2.5,
        label=(
            "Communication-Aware A*"
        ),
    )

    # Start
    ax.scatter(
        [0.0],
        [0.0],
        marker="^",
        s=180,
        zorder=10,
        label="Start",
    )

    # Goal
    goal_east, goal_north = (
        grid_to_local(
            node=GOAL,
            origin_node=START,
            resolution_m=GRID_RESOLUTION_M,
        )
    )

    ax.scatter(
        [goal_east],
        [goal_north],
        marker="*",
        s=260,
        zorder=10,
        label="Goal",
    )

    # Base stations
    ax.scatter(
        [0.0, 60.0],
        [-20.0, 25.0],
        marker="P",
        s=150,
        label="5G Base Station",
    )

    ax.annotate(
        "BS1",
        (0.0, -20.0),
        xytext=(6, 6),
        textcoords="offset points",
    )

    # BS2 is outside the visible planner area,
    # but its coverage still contributes to the Radio Map.

    # --------------------------------------------------------
    # 7. Metrics box
    # --------------------------------------------------------

    metrics_text = (
        "Normal A*\n"
        f"Distance: "
        f"{normal_metrics['path_distance_m']:.1f} m\n"
        f"Mean score: "
        f"{normal_metrics['mean_coverage_score']:.3f}\n"
        f"Min score: "
        f"{normal_metrics['min_coverage_score']:.3f}\n"
        f"Min RSRP: "
        f"{normal_metrics['min_rsrp_dbm']:.1f} dBm\n"
        f"Handovers: "
        f"{normal_metrics['handover_count']}\n"
        "\n"
        "Communication-Aware A*\n"
        f"Distance: "
        f"{communication_metrics['path_distance_m']:.1f} m\n"
        f"Mean score: "
        f"{communication_metrics['mean_coverage_score']:.3f}\n"
        f"Min score: "
        f"{communication_metrics['min_coverage_score']:.3f}\n"
        f"Min RSRP: "
        f"{communication_metrics['min_rsrp_dbm']:.1f} dBm\n"
        f"Handovers: "
        f"{communication_metrics['handover_count']}\n"
        "\n"
        "Trade-off\n"
        f"Distance: "
        f"+{comparison['distance_change_m']:.1f} m "
        f"(+{comparison['distance_change_pct']:.1f}%)\n"
        f"Min score: "
        f"+{comparison['min_coverage_score_gain']:.3f}\n"
        f"Min RSRP: "
        f"+{comparison['min_rsrp_gain_db']:.1f} dB"
    )

    ax.text(
        0.02,
        0.98,
        metrics_text,
        transform=ax.transAxes,
        verticalalignment="top",
        fontsize=9,
        bbox={
            "boxstyle": "round",
            "alpha": 0.85,
        },
    )

    # --------------------------------------------------------
    # 8. Figure formatting
    # --------------------------------------------------------

    ax.set_xlabel(
        "East (m)"
    )

    ax.set_ylabel(
        "North (m)"
    )

    ax.set_title(
        "Normal A* vs Communication-Aware A*\n"
        "5G Coverage-Aware UAV Path Planning"
    )

    ax.set_xlim(
        -7.5,
        42.5,
    )

    ax.set_ylim(
        -22.5,
        17.5,
    )

    ax.grid(
        True,
        alpha=0.25,
    )

    ax.legend(
        loc="lower right"
    )

    fig.tight_layout()

    output_png = (
        OUTPUT_DIR
        / "astar_vs_comm_astar.png"
    )

    fig.savefig(
        output_png,
        dpi=200,
    )

    plt.close(
        fig
    )

    # --------------------------------------------------------
    # 9. Console summary
    # --------------------------------------------------------

    print()
    print(
        "=== Planner Comparison ==="
    )

    print()
    print("Normal A*")
    print(
        f"  Distance: "
        f"{normal_metrics['path_distance_m']:.2f} m"
    )
    print(
        f"  Mean score: "
        f"{normal_metrics['mean_coverage_score']:.3f}"
    )
    print(
        f"  Min score: "
        f"{normal_metrics['min_coverage_score']:.3f}"
    )
    print(
        f"  Min RSRP: "
        f"{normal_metrics['min_rsrp_dbm']:.2f} dBm"
    )

    print()
    print(
        "Communication-Aware A*"
    )
    print(
        f"  Distance: "
        f"{communication_metrics['path_distance_m']:.2f} m"
    )
    print(
        f"  Mean score: "
        f"{communication_metrics['mean_coverage_score']:.3f}"
    )
    print(
        f"  Min score: "
        f"{communication_metrics['min_coverage_score']:.3f}"
    )
    print(
        f"  Min RSRP: "
        f"{communication_metrics['min_rsrp_dbm']:.2f} dBm"
    )

    print()
    print("Trade-off")
    print(
        f"  Extra distance: "
        f"{comparison['distance_change_m']:.2f} m"
    )
    print(
        f"  Distance increase: "
        f"{comparison['distance_change_pct']:.2f}%"
    )
    print(
        f"  Min score gain: "
        f"{comparison['min_coverage_score_gain']:.3f}"
    )
    print(
        f"  Min RSRP gain: "
        f"{comparison['min_rsrp_gain_db']:.2f} dB"
    )

    print()
    print(
        f"[OUTPUT] Figure: "
        f"{output_png}"
    )

    print(
        f"[OUTPUT] JSON: "
        f"{output_json}"
    )


if __name__ == "__main__":
    main()
