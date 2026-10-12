import csv
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np

from communication.radio_map import (
    build_demo_radio_map,
)


ALTITUDE_M = 5.0
GRID_STEP_M = 2.5

EAST_MIN_M = -10.0
EAST_MAX_M = 70.0

NORTH_MIN_M = -30.0
NORTH_MAX_M = 35.0


OUTPUT_DIR = Path(
    "outputs/radio_map"
)


def build_grid():
    east_values = np.arange(
        EAST_MIN_M,
        EAST_MAX_M + GRID_STEP_M,
        GRID_STEP_M,
    )

    north_values = np.arange(
        NORTH_MIN_M,
        NORTH_MAX_M + GRID_STEP_M,
        GRID_STEP_M,
    )

    return (
        east_values,
        north_values,
    )


def generate_radio_map():
    radio_map = (
        build_demo_radio_map()
    )

    (
        east_values,
        north_values,
    ) = build_grid()

    rsrp_grid = np.zeros(
        (
            len(north_values),
            len(east_values),
        )
    )

    sinr_grid = np.zeros_like(
        rsrp_grid
    )

    score_grid = np.zeros_like(
        rsrp_grid
    )

    serving_grid = []

    rows = []

    for north_index, north_m in enumerate(
        north_values
    ):
        serving_row = []

        for east_index, east_m in enumerate(
            east_values
        ):
            result = radio_map.query(
                east_m=float(east_m),
                north_m=float(north_m),
                altitude_m=ALTITUDE_M,
            )

            rsrp_grid[
                north_index,
                east_index,
            ] = result["rsrp_dbm"]

            sinr_grid[
                north_index,
                east_index,
            ] = result["sinr_db"]

            score_grid[
                north_index,
                east_index,
            ] = result[
                "coverage_score"
            ]

            serving_row.append(
                result["serving_bs"]
            )

            rows.append(
                {
                    "east_m":
                        float(east_m),

                    "north_m":
                        float(north_m),

                    "altitude_m":
                        ALTITUDE_M,

                    "serving_bs":
                        result[
                            "serving_bs"
                        ],

                    "distance_m":
                        result[
                            "distance_m"
                        ],

                    "path_loss_db":
                        result[
                            "path_loss_db"
                        ],

                    "rsrp_dbm":
                        result[
                            "rsrp_dbm"
                        ],

                    "sinr_db":
                        result[
                            "sinr_db"
                        ],

                    "coverage_score":
                        result[
                            "coverage_score"
                        ],

                    "coverage_level":
                        result[
                            "coverage_level"
                        ],
                }
            )

        serving_grid.append(
            serving_row
        )

    return {
        "east_values":
            east_values,

        "north_values":
            north_values,

        "rsrp_grid":
            rsrp_grid,

        "sinr_grid":
            sinr_grid,

        "score_grid":
            score_grid,

        "serving_grid":
            serving_grid,

        "rows":
            rows,
    }


def save_csv(
    rows,
    output_path,
):
    fieldnames = [
        "east_m",
        "north_m",
        "altitude_m",
        "serving_bs",
        "distance_m",
        "path_loss_db",
        "rsrp_dbm",
        "sinr_db",
        "coverage_score",
        "coverage_level",
    ]

    with output_path.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()
        writer.writerows(
            rows
        )


def save_heatmap(
    data,
    east_values,
    north_values,
    title,
    colorbar_label,
    output_path,
):
    fig, ax = plt.subplots(
        figsize=(10, 7)
    )

    image = ax.imshow(
        data,
        origin="lower",
        extent=[
            east_values[0],
            east_values[-1],
            north_values[0],
            north_values[-1],
        ],
        aspect="auto",
    )

    colorbar = fig.colorbar(
        image,
        ax=ax,
    )

    colorbar.set_label(
        colorbar_label
    )

    # Base stations
    ax.scatter(
        [0.0, 60.0],
        [-20.0, 25.0],
        marker="^",
        s=160,
        label="5G Base Station",
    )

    ax.annotate(
        "BS1",
        (0.0, -20.0),
        xytext=(6, 6),
        textcoords="offset points",
    )

    ax.annotate(
        "BS2",
        (60.0, 25.0),
        xytext=(6, 6),
        textcoords="offset points",
    )

    # Weak-coverage zone boundary
    rectangle = plt.Rectangle(
        (20.0, 5.0),
        15.0,
        15.0,
        fill=False,
        linewidth=2,
        linestyle="--",
        label="Weak Coverage Zone",
    )

    ax.add_patch(
        rectangle
    )

    # Current A* route
    route_east = [
        0.0,
        10.0,
        10.0,
        35.0,
        35.0,
    ]

    route_north = [
        0.0,
        0.0,
        15.0,
        15.0,
        0.0,
    ]

    ax.plot(
        route_east,
        route_north,
        marker="o",
        linewidth=2,
        linestyle="--",
        label="Current A* Route",
    )

    ax.set_xlabel(
        "East (m)"
    )

    ax.set_ylabel(
        "North (m)"
    )

    ax.set_title(
        title
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


def main():
    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    result = generate_radio_map()

    csv_path = (
        OUTPUT_DIR
        / "radio_map_h5m.csv"
    )

    save_csv(
        result["rows"],
        csv_path,
    )

    save_heatmap(
        result["rsrp_grid"],
        result["east_values"],
        result["north_values"],
        title=(
            "5G RSRP Radio Map "
            "(Altitude = 5 m)"
        ),
        colorbar_label="RSRP (dBm)",
        output_path=(
            OUTPUT_DIR
            / "rsrp_h5m.png"
        ),
    )

    save_heatmap(
        result["sinr_grid"],
        result["east_values"],
        result["north_values"],
        title=(
            "5G SINR Radio Map "
            "(Altitude = 5 m)"
        ),
        colorbar_label="SINR (dB)",
        output_path=(
            OUTPUT_DIR
            / "sinr_h5m.png"
        ),
    )

    save_heatmap(
        result["score_grid"],
        result["east_values"],
        result["north_values"],
        title=(
            "5G Coverage Score Map "
            "(Altitude = 5 m)"
        ),
        colorbar_label=(
            "Coverage Score"
        ),
        output_path=(
            OUTPUT_DIR
            / "coverage_score_h5m.png"
        ),
    )

    print(
        "[RADIO MAP] Generation completed"
    )

    print(
        f"[RADIO MAP] Samples: "
        f"{len(result['rows'])}"
    )

    print(
        f"[RADIO MAP] CSV: "
        f"{csv_path}"
    )

    print(
        "[RADIO MAP] Images:"
    )

    print(
        "  outputs/radio_map/"
        "rsrp_h5m.png"
    )

    print(
        "  outputs/radio_map/"
        "sinr_h5m.png"
    )

    print(
        "  outputs/radio_map/"
        "coverage_score_h5m.png"
    )


if __name__ == "__main__":
    main()
