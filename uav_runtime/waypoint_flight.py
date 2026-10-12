import asyncio
import math
from mavsdk import System

TAKEOFF_ALTITUDE_M = 5.0
WAYPOINT_DISTANCE_M = 10.0
ARRIVAL_THRESHOLD_M = 1.5


def distance_m(lat1, lon1, lat2, lon2):
    radius = 6371000.0

    lat1 = math.radians(lat1)
    lat2 = math.radians(lat2)

    d_lat = lat2 - lat1
    d_lon = math.radians(lon2 - lon1)

    a = (
        math.sin(d_lat / 2) ** 2
        + math.cos(lat1)
        * math.cos(lat2)
        * math.sin(d_lon / 2) ** 2
    )

    return radius * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


async def get_position(drone):
    async for position in drone.telemetry.position():
        return position


async def wait_for_takeoff(drone):
    async for position in drone.telemetry.position():
        altitude = position.relative_altitude_m
        print(f"[ALT] {altitude:.2f} m")

        if altitude >= 4.5:
            print("[OK] Takeoff altitude reached")
            return


async def wait_for_waypoint(drone, target_lat, target_lon):
    async for position in drone.telemetry.position():
        distance = distance_m(
            position.latitude_deg,
            position.longitude_deg,
            target_lat,
            target_lon,
        )

        print(f"[DIST] {distance:.2f} m")

        if distance <= ARRIVAL_THRESHOLD_M:
            print("[OK] Target reached")
            return


async def wait_for_landing(drone):
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            print("[OK] Landed")
            return


async def main():
    drone = System()

    print("[1] Connecting to PX4...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[OK] Connected to PX4")
            break

    print("[2] Waiting for position data...")

    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("[OK] Position ready")
            break

    home = await get_position(drone)

    home_lat = home.latitude_deg
    home_lon = home.longitude_deg
    home_alt = home.absolute_altitude_m

    print(
        f"[HOME] lat={home_lat:.7f}, "
        f"lon={home_lon:.7f}"
    )

    # 构造一个大约位于起飞点北侧 10 m 的航点
    waypoint_lat = home_lat + WAYPOINT_DISTANCE_M / 111320.0
    waypoint_lon = home_lon

    flight_altitude = home_alt + TAKEOFF_ALTITUDE_M

    print(
        f"[WAYPOINT] lat={waypoint_lat:.7f}, "
        f"lon={waypoint_lon:.7f}"
    )

    print("[3] Setting takeoff altitude...")
    await drone.action.set_takeoff_altitude(TAKEOFF_ALTITUDE_M)

    print("[4] Arming...")
    await drone.action.arm()

    print("[5] Taking off...")
    await drone.action.takeoff()

    await wait_for_takeoff(drone)

    print("[6] Flying 10 m north...")
    await drone.action.goto_location(
        waypoint_lat,
        waypoint_lon,
        flight_altitude,
        0.0,
    )

    await wait_for_waypoint(
        drone,
        waypoint_lat,
        waypoint_lon,
    )

    print("[7] Hovering for 5 seconds...")
    await asyncio.sleep(5)

    print("[8] Returning home...")
    await drone.action.goto_location(
        home_lat,
        home_lon,
        flight_altitude,
        180.0,
    )

    await wait_for_waypoint(
        drone,
        home_lat,
        home_lon,
    )

    print("[9] Hovering for 3 seconds...")
    await asyncio.sleep(3)

    print("[10] Landing...")
    await drone.action.land()

    await wait_for_landing(drone)

    print("[DONE] Single-waypoint mission completed")


if __name__ == "__main__":
    asyncio.run(main())
