import csv
import json
import math
from pathlib import Path


def point_distance(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
) -> float:
    return math.hypot(
        x2 - x1,
        y2 - y1,
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
                    "elapsed_s":
                        float(row["elapsed_s"]),

                    "east_m":
                        float(row["east_m"]),

                    "north_m":
                        float(row["north_m"]),

                    "in_air":
                        row["in_air"].lower()
                        == "true",

                    "target_waypoint":
                        row["target_waypoint"],
                }
            )

    return trajectory


def calculate_planned_distance(
    waypoints,
):
    total = 0.0

    for index in range(
        len(waypoints) - 1
    ):
        current = waypoints[index]
        next_point = waypoints[index + 1]

        total += point_distance(
            current["east_m"],
            current["north_m"],
            next_point["east_m"],
            next_point["north_m"],
        )

    return total


def calculate_actual_distance(
    trajectory,
):
    total = 0.0

    for index in range(
        len(trajectory) - 1
    ):
        current = trajectory[index]
        next_point = trajectory[index + 1]

        total += point_distance(
            current["east_m"],
            current["north_m"],
            next_point["east_m"],
            next_point["north_m"],
        )

    return total


def point_to_segment_distance(
    px,
    py,
    ax,
    ay,
    bx,
    by,
):
    ab_x = bx - ax
    ab_y = by - ay

    ap_x = px - ax
    ap_y = py - ay

    ab_squared = (
        ab_x ** 2
        + ab_y ** 2
    )

    if ab_squared == 0:
        return point_distance(
            px,
            py,
            ax,
            ay,
        )

    projection = (
        ap_x * ab_x
        + ap_y * ab_y
    ) / ab_squared

    projection = max(
        0.0,
        min(
            1.0,
            projection,
        ),
    )

    nearest_x = (
        ax
        + projection * ab_x
    )

    nearest_y = (
        ay
        + projection * ab_y
    )

    return point_distance(
        px,
        py,
        nearest_x,
        nearest_y,
    )


def calculate_path_deviations(
    trajectory,
    waypoints,
):
    deviations = []

    for sample in trajectory:

        minimum_distance = math.inf

        for index in range(
            len(waypoints) - 1
        ):
            start = waypoints[index]
            end = waypoints[index + 1]

            distance = (
                point_to_segment_distance(
                    sample["east_m"],
                    sample["north_m"],
                    start["east_m"],
                    start["north_m"],
                    end["east_m"],
                    end["north_m"],
                )
            )

            minimum_distance = min(
                minimum_distance,
                distance,
            )

        deviations.append(
            minimum_distance
        )

    return deviations


def calculate_waypoint_errors(
    trajectory,
    waypoints,
):
    errors = {}

    # WP0 is the mission start.
    # Evaluate WP1 ... WP4.
    for waypoint in waypoints[1:]:

        waypoint_id = (
            waypoint["waypoint_id"]
        )

        matching_samples = [
            sample
            for sample in trajectory
            if (
                sample["target_waypoint"]
                == waypoint_id
            )
        ]

        if not matching_samples:
            continue

        minimum_error = min(
            point_distance(
                sample["east_m"],
                sample["north_m"],
                waypoint["east_m"],
                waypoint["north_m"],
            )
            for sample in matching_samples
        )

        errors[waypoint_id] = (
            minimum_error
        )

    return errors


def calculate_metrics(
    planned_waypoints,
    actual_trajectory,
):
    planned_distance = (
        calculate_planned_distance(
            planned_waypoints
        )
    )

    actual_distance = (
        calculate_actual_distance(
            actual_trajectory
        )
    )

    mission_duration = (
        actual_trajectory[-1]["elapsed_s"]
        - actual_trajectory[0]["elapsed_s"]
    )

    waypoint_errors = (
        calculate_waypoint_errors(
            actual_trajectory,
            planned_waypoints,
        )
    )

    waypoint_error_values = list(
        waypoint_errors.values()
    )

    if waypoint_error_values:

        mean_waypoint_error = (
            sum(waypoint_error_values)
            / len(waypoint_error_values)
        )

        max_waypoint_error = max(
            waypoint_error_values
        )

    else:

        mean_waypoint_error = None
        max_waypoint_error = None

    deviations = (
        calculate_path_deviations(
            actual_trajectory,
            planned_waypoints,
        )
    )

    mean_path_deviation = (
        sum(deviations)
        / len(deviations)
    )

    max_path_deviation = max(
        deviations
    )

    if actual_distance > 0:

        flight_efficiency = (
            planned_distance
            / actual_distance
        )

    else:

        flight_efficiency = None

    metrics = {
        "planned_distance_m":
            planned_distance,

        "actual_distance_m":
            actual_distance,

        "mission_duration_s":
            mission_duration,

        "waypoint_errors_m":
            waypoint_errors,

        "mean_waypoint_error_m":
            mean_waypoint_error,

        "max_waypoint_error_m":
            max_waypoint_error,

        "mean_path_deviation_m":
            mean_path_deviation,

        "max_path_deviation_m":
            max_path_deviation,

        "flight_efficiency":
            flight_efficiency,
    }

    return metrics


def find_latest_run():
    runs_dir = Path(
        "outputs/runs"
    )

    run_dirs = [
        path
        for path in runs_dir.iterdir()
        if path.is_dir()
    ]

    if not run_dirs:
        raise FileNotFoundError(
            "No mission run found"
        )

    return max(
        run_dirs,
        key=lambda path:
            path.stat().st_mtime,
    )


def main():
    run_dir = find_latest_run()

    planned_csv = (
        run_dir
        / "planned_waypoints.csv"
    )

    actual_csv = (
        run_dir
        / "actual_trajectory.csv"
    )

    print(
        f"[RUN] Using: {run_dir}"
    )

    planned_waypoints = (
        load_planned_waypoints(
            planned_csv
        )
    )

    actual_trajectory = (
        load_actual_trajectory(
            actual_csv
        )
    )

    metrics = calculate_metrics(
        planned_waypoints,
        actual_trajectory,
    )

    print("\n=== Mission Metrics ===")

    print(
        "Planned distance: "
        f"{metrics['planned_distance_m']:.2f} m"
    )

    print(
        "Actual distance: "
        f"{metrics['actual_distance_m']:.2f} m"
    )

    print(
        "Mission duration: "
        f"{metrics['mission_duration_s']:.2f} s"
    )

    print("\nWaypoint errors:")

    for waypoint_id, error in (
        metrics["waypoint_errors_m"].items()
    ):
        print(
            f"  {waypoint_id}: "
            f"{error:.3f} m"
        )

    print(
        "\nMean waypoint error: "
        f"{metrics['mean_waypoint_error_m']:.3f} m"
    )

    print(
        "Max waypoint error: "
        f"{metrics['max_waypoint_error_m']:.3f} m"
    )

    print(
        "Mean path deviation: "
        f"{metrics['mean_path_deviation_m']:.3f} m"
    )

    print(
        "Max path deviation: "
        f"{metrics['max_path_deviation_m']:.3f} m"
    )

    print(
        "Flight efficiency: "
        f"{metrics['flight_efficiency'] * 100:.2f}%"
    )

    output_json = (
        run_dir
        / "mission_summary.json"
    )

    with output_json.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            metrics,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print(
        f"\n[OK] Summary saved: "
        f"{output_json}"
    )


if __name__ == "__main__":
    main()
