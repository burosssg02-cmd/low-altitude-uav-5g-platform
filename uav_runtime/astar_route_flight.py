import asyncio
import csv
import math
import time

from datetime import datetime
from pathlib import Path

from mavsdk import System

from planner.astar import astar_search
from planner.grid_map import GridMap
from planner.path_utils import simplify_path
from planner.waypoint_builder import build_gps_waypoints

from uav_runtime.telemetry_recorder import TelemetryRecorder


TAKEOFF_ALTITUDE_M = 5.0
GRID_RESOLUTION_M = 5.0

ARRIVAL_THRESHOLD_M = 1.5
WAYPOINT_TIMEOUT_S = 60.0


def horizontal_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate horizontal distance between two GPS coordinates.
    """

    radius = 6371000.0

    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)

    delta_lat = math.radians(
        lat2 - lat1
    )

    delta_lon = math.radians(
        lon2 - lon1
    )

    a = (
        math.sin(delta_lat / 2.0) ** 2
        + math.cos(lat1_rad)
        * math.cos(lat2_rad)
        * math.sin(delta_lon / 2.0) ** 2
    )

    c = 2.0 * math.atan2(
        math.sqrt(a),
        math.sqrt(1.0 - a),
    )

    return radius * c


async def get_position(drone):
    """
    Get one PX4 position sample.
    """

    async for position in drone.telemetry.position():
        return position


async def wait_for_takeoff(
    drone,
    target_altitude_m: float,
):
    """
    Wait until UAV reaches takeoff altitude.
    """

    last_print_time = 0.0

    async for position in drone.telemetry.position():

        altitude = (
            position.relative_altitude_m
        )

        now = time.monotonic()

        if (
            now - last_print_time
            >= 0.5
        ):
            print(
                f"[ALT] "
                f"{altitude:.2f} m"
            )

            last_print_time = now

        if (
            altitude
            >= target_altitude_m - 0.5
        ):
            print(
                "[OK] Takeoff altitude reached"
            )

            return


async def wait_for_waypoint(
    drone,
    target_lat: float,
    target_lon: float,
    waypoint_index: int,
):
    """
    Wait until UAV reaches target waypoint.
    """

    start_time = time.monotonic()
    last_print_time = 0.0

    async for position in drone.telemetry.position():

        distance = horizontal_distance_m(
            position.latitude_deg,
            position.longitude_deg,
            target_lat,
            target_lon,
        )

        now = time.monotonic()

        if (
            now - last_print_time
            >= 0.5
        ):
            print(
                f"[WP{waypoint_index}] "
                f"distance={distance:.2f} m"
            )

            last_print_time = now

        if (
            distance
            <= ARRIVAL_THRESHOLD_M
        ):
            print(
                f"[OK] WP{waypoint_index} reached"
            )

            return

        if (
            now - start_time
            >= WAYPOINT_TIMEOUT_S
        ):
            raise TimeoutError(
                f"WP{waypoint_index} timeout"
            )


async def wait_for_landing(drone):
    """
    Wait until PX4 reports that UAV is no longer in air.
    """

    async for in_air in drone.telemetry.in_air():

        if not in_air:
            print("[OK] Landed")
            return


def save_planned_waypoints(
    waypoints,
    output_path,
):
    """
    Save planned A* GPS waypoints to CSV.
    """

    output_path = Path(
        output_path
    )

    output_path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fieldnames = [
        "waypoint_id",
        "grid_x",
        "grid_y",
        "east_m",
        "north_m",
        "latitude_deg",
        "longitude_deg",
        "relative_altitude_m",
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

        for waypoint in waypoints:

            writer.writerow(
                {
                    "waypoint_id":
                        f"WP{waypoint.index}",

                    "grid_x":
                        waypoint.grid_x,

                    "grid_y":
                        waypoint.grid_y,

                    "east_m":
                        waypoint.east_m,

                    "north_m":
                        waypoint.north_m,

                    "latitude_deg":
                        waypoint.latitude_deg,

                    "longitude_deg":
                        waypoint.longitude_deg,

                    "relative_altitude_m":
                        waypoint.relative_altitude_m,
                }
            )

    print(
        f"[OUTPUT] Planned waypoints saved: "
        f"{output_path}"
    )


async def main():

    # =====================================================
    # 1. Create run directory
    # =====================================================

    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    run_dir = (
        Path("outputs")
        / "runs"
        / run_id
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    planned_waypoints_csv = (
        run_dir
        / "planned_waypoints.csv"
    )

    actual_trajectory_csv = (
        run_dir
        / "actual_trajectory.csv"
    )

    print(
        f"[RUN] Mission ID: "
        f"{run_id}"
    )

    print(
        f"[RUN] Output directory: "
        f"{run_dir}"
    )

    # =====================================================
    # 2. Build virtual planning map
    # =====================================================

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

    print(
        "\n[1] Running A* planner..."
    )

    raw_path = astar_search(
        grid_map,
        start,
        goal,
    )

    simplified_path = simplify_path(
        raw_path
    )

    print(
        f"[A*] Raw path: "
        f"{raw_path}"
    )

    print(
        f"[A*] Simplified: "
        f"{simplified_path}"
    )

    print(
        f"[A*] Nodes: "
        f"{len(raw_path)} -> "
        f"{len(simplified_path)}"
    )

    # =====================================================
    # 3. Connect MAVSDK to PX4
    # =====================================================

    drone = System()

    print(
        "\n[2] Connecting to PX4..."
    )

    await drone.connect(
        system_address=(
            "udpin://0.0.0.0:14540"
        )
    )

    async for state in (
        drone.core.connection_state()
    ):

        if state.is_connected:

            print(
                "[OK] Connected to PX4"
            )

            break

    # =====================================================
    # 4. Wait for position
    # =====================================================

    print(
        "[3] Waiting for position..."
    )

    async for health in (
        drone.telemetry.health()
    ):

        if (
            health.is_global_position_ok
            and health.is_home_position_ok
        ):
            print(
                "[OK] Position ready"
            )

            break

    # =====================================================
    # 5. Read actual PX4 home position
    # =====================================================

    home = await get_position(
        drone
    )

    home_lat = (
        home.latitude_deg
    )

    home_lon = (
        home.longitude_deg
    )

    home_absolute_altitude = (
        home.absolute_altitude_m
    )

    print(
        f"[HOME] "
        f"lat={home_lat:.7f}, "
        f"lon={home_lon:.7f}, "
        f"alt={home_absolute_altitude:.2f} m"
    )

    # =====================================================
    # 6. Convert A* route to GPS waypoints
    # =====================================================

    waypoints = build_gps_waypoints(
        path=simplified_path,
        origin_node=start,
        origin_lat_deg=home_lat,
        origin_lon_deg=home_lon,
        resolution_m=GRID_RESOLUTION_M,
        relative_altitude_m=TAKEOFF_ALTITUDE_M,
    )

    print(
        "\n[4] GPS waypoints:"
    )

    for waypoint in waypoints:

        print(
            f"WP{waypoint.index}: "
            f"grid=({waypoint.grid_x}, "
            f"{waypoint.grid_y}) | "
            f"E={waypoint.east_m:.1f} m, "
            f"N={waypoint.north_m:.1f} m | "
            f"lat={waypoint.latitude_deg:.7f}, "
            f"lon={waypoint.longitude_deg:.7f}"
        )

    # =====================================================
    # 7. Save planned route
    # =====================================================

    save_planned_waypoints(
        waypoints=waypoints,
        output_path=planned_waypoints_csv,
    )

    target_absolute_altitude = (
        home_absolute_altitude
        + TAKEOFF_ALTITUDE_M
    )

    # =====================================================
    # 8. Create TelemetryRecorder
    # =====================================================

    recorder = TelemetryRecorder(
        drone=drone,
        origin_lat_deg=home_lat,
        origin_lon_deg=home_lon,
        sample_interval_s=0.2,
    )

    mission_started = False

    try:

        # =================================================
        # 9. Start telemetry recording
        # =================================================

        print(
            "\n[5] Starting telemetry recorder..."
        )

        recorder.set_target_waypoint(
            "TAKEOFF"
        )

        await recorder.start()

        # =================================================
        # 10. Takeoff
        # =================================================

        print(
            "[6] Setting takeoff altitude..."
        )

        await drone.action.set_takeoff_altitude(
            TAKEOFF_ALTITUDE_M
        )

        print(
            "[7] Arming..."
        )

        await drone.action.arm()

        mission_started = True

        print(
            "[8] Taking off..."
        )

        await drone.action.takeoff()

        await wait_for_takeoff(
            drone,
            TAKEOFF_ALTITUDE_M,
        )

        # =================================================
        # 11. Execute A* route
        # =================================================

        print(
            "\n[9] Starting A* route..."
        )

        # WP0 is the home/start point.
        # UAV is already above WP0 after takeoff.
        for waypoint in waypoints[1:]:

            waypoint_name = (
                f"WP{waypoint.index}"
            )

            recorder.set_target_waypoint(
                waypoint_name
            )

            print(
                f"\n[MOVE] Flying to "
                f"{waypoint_name}"
            )

            await drone.action.goto_location(
                waypoint.latitude_deg,
                waypoint.longitude_deg,
                target_absolute_altitude,
                0.0,
            )

            await wait_for_waypoint(
                drone,
                waypoint.latitude_deg,
                waypoint.longitude_deg,
                waypoint.index,
            )

            print(
                f"[HOVER] "
                f"{waypoint_name} "
                f"for 2 seconds"
            )

            await asyncio.sleep(
                2
            )

        # =================================================
        # 12. Land at A* goal
        # =================================================

        print(
            "\n[10] Goal reached"
        )

        recorder.set_target_waypoint(
            "LANDING"
        )

        print(
            "[11] Landing at goal..."
        )

        await drone.action.land()

        await wait_for_landing(
            drone
        )

        # Allow background telemetry tasks to receive
        # the final landed / disarmed state.
        recorder.set_target_waypoint(
            "LANDED"
        )

        print(
            "[RECORDER] Waiting for final "
            "landed telemetry..."
        )

        await asyncio.sleep(
            1.5
        )

        mission_started = False

        print(
            "\n[DONE] "
            "A* route mission completed"
        )

    except Exception as exc:

        print(
            f"\n[ERROR] Mission failed: "
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        # If an exception occurs while the UAV may
        # still be airborne, request a landing.
        if mission_started:

            try:

                print(
                    "[SAFETY] "
                    "Requesting emergency landing..."
                )

                recorder.set_target_waypoint(
                    "EMERGENCY_LANDING"
                )

                await drone.action.land()

                await wait_for_landing(
                    drone
                )

                recorder.set_target_waypoint(
                    "LANDED"
                )

                await asyncio.sleep(
                    1.5
                )

            except Exception as landing_exc:

                print(
                    f"[SAFETY] Landing failed: "
                    f"{landing_exc}"
                )

        raise

    finally:

        # =================================================
        # 13. Stop recorder and save trajectory
        # =================================================

        await recorder.stop()

        recorder.save_csv(
            actual_trajectory_csv
        )

        print(
            "\n[OUTPUT] Mission files:"
        )

        print(
            f"  Planned: "
            f"{planned_waypoints_csv}"
        )

        print(
            f"  Actual:  "
            f"{actual_trajectory_csv}"
        )

        print(
            f"  Run dir: "
            f"{run_dir}"
        )


if __name__ == "__main__":
    asyncio.run(main())
