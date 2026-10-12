import asyncio

from uav_runtime.dynamic_route_controller import (
    DynamicRouteController,
)


def make_route():
    return [
        {"name": "WP1"},
        {"name": "WP2"},
        {"name": "WP3"},
    ]


def test_initial_route_order():
    controller = DynamicRouteController(
        make_route()
    )

    assert (
        controller.remaining_count
        == 3
    )

    assert (
        controller.pop_next()["name"]
        == "WP1"
    )

    assert (
        controller.pop_next()["name"]
        == "WP2"
    )


def test_request_and_apply_replan():
    controller = DynamicRouteController(
        make_route()
    )

    # WP1 is already being executed.
    first = controller.pop_next()

    assert first["name"] == "WP1"

    replacement = [
        {"name": "RWP1"},
        {"name": "RWP2"},
        {"name": "GOAL"},
    ]

    accepted = (
        controller.request_replan(
            new_waypoints=replacement,
            reason="communication degraded",
        )
    )

    assert accepted is True

    assert (
        controller.has_pending_replan
        is True
    )

    assert (
        controller.replan_event.is_set()
        is True
    )

    metadata = (
        controller.apply_pending_replan()
    )

    assert (
        metadata["waypoint_count"]
        == 3
    )

    assert (
        controller.has_pending_replan
        is False
    )

    assert (
        controller.applied_replans
        == 1
    )

    assert (
        controller.pop_next()["name"]
        == "RWP1"
    )


def test_duplicate_pending_replan_rejected():
    controller = DynamicRouteController(
        make_route()
    )

    assert controller.request_replan(
        [{"name": "R1"}],
        "first",
    )

    accepted = controller.request_replan(
        [{"name": "R2"}],
        "second",
    )

    assert accepted is False

    assert (
        controller.requested_replans
        == 1
    )


def test_cancel_pending_replan():
    controller = DynamicRouteController(
        make_route()
    )

    controller.request_replan(
        [{"name": "R1"}],
        "test",
    )

    assert (
        controller.cancel_pending_replan()
        is True
    )

    assert (
        controller.has_pending_replan
        is False
    )

    assert (
        controller.replan_event.is_set()
        is False
    )


def test_event_can_be_waited():
    async def scenario():
        controller = (
            DynamicRouteController(
                make_route()
            )
        )

        async def trigger():
            await asyncio.sleep(
                0.01
            )

            controller.request_replan(
                [{"name": "R1"}],
                "runtime incident",
            )

        task = asyncio.create_task(
            trigger()
        )

        await asyncio.wait_for(
            controller.replan_event.wait(),
            timeout=1.0,
        )

        await task

        assert (
            controller.has_pending_replan
            is True
        )

    asyncio.run(
        scenario()
    )
