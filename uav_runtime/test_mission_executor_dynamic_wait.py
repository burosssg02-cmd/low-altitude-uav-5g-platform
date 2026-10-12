import asyncio

from uav_runtime.dynamic_route_controller import (
    DynamicRouteController,
)
import uav_runtime.mission_executor as executor


class FakeDrone:
    pass


def test_wait_returns_waypoint_reached(monkeypatch):
    async def fake_wait_for_waypoint(
        drone,
        target_lat,
        target_lon,
        waypoint_name,
    ):
        await asyncio.sleep(0.01)

    monkeypatch.setattr(
        executor,
        "wait_for_waypoint",
        fake_wait_for_waypoint,
    )

    async def scenario():
        controller = DynamicRouteController(
            [{"name": "WP1"}]
        )

        result = await (
            executor.wait_for_waypoint_or_replan(
                drone=FakeDrone(),
                target_lat=30.0,
                target_lon=114.0,
                waypoint_name="WP1",
                route_controller=controller,
            )
        )

        assert result == "WAYPOINT_REACHED"

    asyncio.run(scenario())


def test_wait_returns_replan_pending(monkeypatch):
    async def slow_wait_for_waypoint(
        drone,
        target_lat,
        target_lon,
        waypoint_name,
    ):
        await asyncio.sleep(10)

    monkeypatch.setattr(
        executor,
        "wait_for_waypoint",
        slow_wait_for_waypoint,
    )

    async def scenario():
        controller = DynamicRouteController(
            [{"name": "WP1"}]
        )

        async def trigger():
            await asyncio.sleep(0.01)

            controller.request_replan(
                new_waypoints=[
                    {"name": "RWP1"},
                ],
                reason="test runtime replan",
            )

        trigger_task = asyncio.create_task(
            trigger()
        )

        result = await (
            executor.wait_for_waypoint_or_replan(
                drone=FakeDrone(),
                target_lat=30.0,
                target_lon=114.0,
                waypoint_name="WP1",
                route_controller=controller,
            )
        )

        await trigger_task

        assert result == "REPLAN_PENDING"

    asyncio.run(scenario())
