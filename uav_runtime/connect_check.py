import asyncio
from mavsdk import System


async def main():
    drone = System()

    print("[1] Connecting to PX4...")
    await drone.connect(system_address="udpin://0.0.0.0:14540")

    print("[2] Waiting for connection...")
    async for state in drone.core.connection_state():
        if state.is_connected:
            print("[OK] MAVSDK connected to PX4")
            break

    print("[3] Waiting for position data...")
    async for health in drone.telemetry.health():
        print(
            f"global_position={health.is_global_position_ok}, "
            f"home_position={health.is_home_position_ok}"
        )

        if health.is_global_position_ok and health.is_home_position_ok:
            print("[OK] PX4 position and home position are ready")
            break


if __name__ == "__main__":
    asyncio.run(main())
