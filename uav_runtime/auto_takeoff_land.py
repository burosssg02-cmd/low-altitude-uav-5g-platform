import asyncio
from mavsdk import System


async def main():
    drone = System()

    print("[1] Connecting to PX4...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    print("[2] Waiting for connection...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[OK] Connected to PX4")
            break

    print("[3] Waiting for position...")
    async for health in drone.telemetry.health():
        if health.is_global_position_ok and health.is_home_position_ok:
            print("[OK] Position ready")
            break

    print("[4] Setting takeoff altitude to 5 m...")
    await drone.action.set_takeoff_altitude(5.0)

    print("[5] Arming...")
    await drone.action.arm()

    print("[6] Taking off...")
    await drone.action.takeoff()

    print("[7] Waiting until altitude reaches about 5 m...")
    async for position in drone.telemetry.position():
        altitude = position.relative_altitude_m
        print(f"Altitude: {altitude:.2f} m")

        if altitude >= 4.5:
            print("[OK] Takeoff altitude reached")
            break

    print("[8] Hovering for 10 seconds...")
    await asyncio.sleep(10)

    print("[9] Landing...")
    await drone.action.land()

    print("[10] Waiting for landing...")
    async for in_air in drone.telemetry.in_air():
        if not in_air:
            print("[OK] Landed")
            break

    print("[DONE] Mission completed")


if __name__ == "__main__":
    asyncio.run(main())
