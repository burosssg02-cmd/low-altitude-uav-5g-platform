import csv
import json
from pathlib import Path

from communication.radio_map import (
    build_demo_radio_map,
)


def load_trajectory(
    csv_path,
):
    rows = []

    with open(
        csv_path,
        "r",
        encoding="utf-8",
    ) as file:

        reader = csv.DictReader(
            file
        )

        for row in reader:
            rows.append(
                {
                    "elapsed_s":
                        float(
                            row["elapsed_s"]
                        ),

                    "east_m":
                        float(
                            row["east_m"]
                        ),

                    "north_m":
                        float(
                            row["north_m"]
                        ),

                    "altitude_m":
                        float(
                            row["relative_altitude_m"]
                        ),

                    "in_air":
                        row["in_air"].lower()
                        == "true",
                }
            )

    return rows


def evaluate_communication(
    run_dir,
):
    run_dir = Path(
        run_dir
    )

    trajectory_csv = (
        run_dir
        / "actual_trajectory.csv"
    )

    output_csv = (
        run_dir
        / "trajectory_communication.csv"
    )

    summary_json = (
        run_dir
        / "communication_summary.json"
    )

    trajectory = load_trajectory(
        trajectory_csv
    )

    if not trajectory:
        raise ValueError(
            "Trajectory is empty"
        )

    radio_map = (
        build_demo_radio_map()
    )

    results = []

    for sample in trajectory:

        radio_result = radio_map.query(
            east_m=sample["east_m"],
            north_m=sample["north_m"],
            altitude_m=max(
                sample["altitude_m"],
                0.0,
            ),
        )

        results.append(
            {
                **sample,
                **radio_result,
            }
        )

    fieldnames = [
        "elapsed_s",
        "east_m",
        "north_m",
        "altitude_m",
        "in_air",
        "serving_bs",
        "distance_m",
        "path_loss_db",
        "rsrp_dbm",
        "sinr_db",
        "coverage_score",
        "coverage_level",
    ]

    with output_csv.open(
        "w",
        newline="",
        encoding="utf-8",
    ) as file:

        writer = csv.DictWriter(
            file,
            fieldnames=fieldnames,
        )

        writer.writeheader()

        for result in results:

            writer.writerow(
                {
                    key:
                        result[key]
                    for key
                    in fieldnames
                }
            )

    # Only evaluate communication while airborne.
    airborne_results = [
        result
        for result in results
        if result["in_air"]
    ]

    if not airborne_results:
        airborne_results = results

    rsrp_values = [
        result["rsrp_dbm"]
        for result
        in airborne_results
    ]

    sinr_values = [
        result["sinr_db"]
        for result
        in airborne_results
    ]

    score_values = [
        result["coverage_score"]
        for result
        in airborne_results
    ]

    poor_samples = [
        result
        for result
        in airborne_results
        if result["coverage_level"]
        == "POOR"
    ]

    fair_or_poor_samples = [
        result
        for result
        in airborne_results
        if result["coverage_level"]
        != "GOOD"
    ]

    handover_count = 0

    previous_bs = None

    for result in airborne_results:

        current_bs = (
            result["serving_bs"]
        )

        if (
            previous_bs is not None
            and current_bs != previous_bs
        ):
            handover_count += 1

        previous_bs = current_bs

    summary = {
        "samples":
            len(airborne_results),

        "mean_rsrp_dbm":
            sum(rsrp_values)
            / len(rsrp_values),

        "min_rsrp_dbm":
            min(rsrp_values),

        "mean_sinr_db":
            sum(sinr_values)
            / len(sinr_values),

        "min_sinr_db":
            min(sinr_values),

        "mean_coverage_score":
            sum(score_values)
            / len(score_values),

        "min_coverage_score":
            min(score_values),

        "poor_sample_ratio":
            len(poor_samples)
            / len(airborne_results),

        "non_good_sample_ratio":
            len(
                fair_or_poor_samples
            )
            / len(
                airborne_results
            ),

        "handover_count":
            handover_count,
    }

    with summary_json.open(
        "w",
        encoding="utf-8",
    ) as file:

        json.dump(
            summary,
            file,
            indent=2,
            ensure_ascii=False,
        )

    print(
        f"[COMM] Samples: "
        f"{summary['samples']}"
    )

    print(
        f"[COMM] Mean RSRP: "
        f"{summary['mean_rsrp_dbm']:.2f} dBm"
    )

    print(
        f"[COMM] Min RSRP: "
        f"{summary['min_rsrp_dbm']:.2f} dBm"
    )

    print(
        f"[COMM] Mean SINR: "
        f"{summary['mean_sinr_db']:.2f} dB"
    )

    print(
        f"[COMM] Min SINR: "
        f"{summary['min_sinr_db']:.2f} dB"
    )

    print(
        f"[COMM] Mean score: "
        f"{summary['mean_coverage_score']:.3f}"
    )

    print(
        f"[COMM] Min score: "
        f"{summary['min_coverage_score']:.3f}"
    )

    print(
        f"[COMM] Handover count: "
        f"{summary['handover_count']}"
    )

    print(
        f"[COMM] CSV: "
        f"{output_csv}"
    )

    print(
        f"[COMM] Summary: "
        f"{summary_json}"
    )

    return summary
