import asyncio

from datetime import datetime
from pathlib import Path

from mavsdk import System

from uav_runtime.telemetry_recorder import (
    TelemetryRecorder,
)


async def get_position(drone):
    async for position in drone.telemetry.position():
        return position


async def main():
    drone = System()

    print("[1] Connecting to PX4...")

    await drone.connect(
        system_address="udpin://0.0.0.0:14540"
    )

    async for state in drone.core.connection_state():

        if state.is_connected:
            print("[OK] Connected to PX4")
            break

    print("[2] Waiting for position data...")

    async for health in drone.telemetry.health():

        if (
            health.is_global_position_ok
            and health.is_home_position_ok
        ):
            print("[OK] Position ready")
            break

    position = await get_position(drone)

    origin_lat = position.latitude_deg
    origin_lon = position.longitude_deg

    print(
        f"[ORIGIN] "
        f"lat={origin_lat:.7f}, "
        f"lon={origin_lon:.7f}"
    )

    run_id = datetime.now().strftime(
        "%Y%m%d_%H%M%S"
    )

    run_dir = (
        Path("outputs")
        / "runs"
        / run_id
    )

    output_csv = (
        run_dir
        / "actual_trajectory.csv"
    )

    recorder = TelemetryRecorder(
        drone=drone,
        origin_lat_deg=origin_lat,
        origin_lon_deg=origin_lon,
        sample_interval_s=0.2,
    )

    recorder.set_target_waypoint(
        "STATIC_TEST"
    )

    print("[3] Recording for 10 seconds...")

    await recorder.start()

    await asyncio.sleep(10)

    await recorder.stop()

    recorder.save_csv(
        output_csv
    )

    print(
        f"[DONE] Test run directory: "
        f"{run_dir}"
    )


if __name__ == "__main__":
    asyncio.run(main())
