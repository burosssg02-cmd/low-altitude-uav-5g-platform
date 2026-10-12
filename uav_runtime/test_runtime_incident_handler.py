import asyncio

from communication.radio_map import (
    build_demo_radio_map,
)

from planner.grid_map import (
    GridMap,
)

from uav_runtime.dynamic_route_controller import (
    DynamicRouteController,
)

from uav_runtime.runtime_incident_handler import (
    RuntimeIncidentHandler,
)


OBSTACLES = {
    (4, 1),
    (4, 2),
    (4, 3),
    (4, 4),
    (4, 5),
    (4, 6),
}


EVENT = {
    "event_type":
        "COMMUNICATION_DEGRADED",

    "east_m": 22.4,
    "north_m": 14.9,
    "altitude_m": 5.0,

    "rsrp_dbm": -97.9,
    "sinr_db": 1.9,
    "coverage_score": 0.491,

    "serving_bs": "BS1",

    "reasons": [
        "LOW_RSRP",
        "LOW_COVERAGE_SCORE",
    ],
}


def make_controller():
    return DynamicRouteController(
        [
            {
                "name": "OLD_WP",
                "latitude_deg": 30.0,
                "longitude_deg": 114.0,
            }
        ]
    )


def exploding_agent(
    context,
    verbose=False,
):
    raise AssertionError(
        "LLM Agent must not be called "
        "by the flight-critical path"
    )


def noop_advisor(
    context,
    fast_decision,
    comparison,
    verbose=False,
):
    return {
        "status":
            "COMPLETED",

        "advisory": {
            "severity":
                "INFO",

            "diagnosis":
                "Test advisory.",

            "decision_explanation":
                "Test explanation.",

            "recommended_followup":
                "No action.",

            "confidence":
                1.0,
        },
    }


def make_handler(
    *,
    controller,
    planner="normal",
    is_degraded=lambda: True,
    get_current_local_position=None,
    advisor_runner=noop_advisor,
):
    return RuntimeIncidentHandler(
        mission_id="mission_test",

        mission_start=(1, 3),
        mission_goal=(8, 3),

        planner=planner,

        altitude_m=5.0,

        communication_weight=2.0,

        origin_lat_deg=30.0,
        origin_lon_deg=114.0,

        grid_map=GridMap(
            width=10,
            height=8,
            obstacles=OBSTACLES,
        ),

        radio_map=(
            build_demo_radio_map()
        ),

        resolution_m=5.0,

        route_controller=controller,

        is_degraded=is_degraded,

        get_current_local_position=(
            get_current_local_position
        ),

        # This must NEVER be reached by
        # the flight-critical path.
        agent_runner=exploding_agent,

        advisor_runner=(
            advisor_runner
        ),
    )


def test_degraded_event_queues_replan():
    async def scenario():
        controller = (
            make_controller()
        )

        handler = make_handler(
            controller=controller,
        )

        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        assert (
            result["action"]
            == "REPLAN_QUEUED"
        )

        assert (
            result["decision_source"]
            == "FAST_POLICY"
        )

        assert (
            result["decision"]["decision"]
            == "REPLAN_RECOMMENDED"
        )

        assert (
            controller
            .has_pending_replan
            is True
        )

        metadata = (
            controller
            .apply_pending_replan()
        )

        assert metadata is not None

        first = (
            controller.pop_next()
        )

        assert (
            first["grid_x"],
            first["grid_y"],
        ) == (
            5,
            1,
        )

        assert (
            first["east_m"]
            == 20.0
        )

        assert (
            first["north_m"]
            == 10.0
        )

    asyncio.run(
        scenario()
    )


def test_communication_aware_route_kept():
    async def scenario():
        controller = (
            make_controller()
        )

        handler = make_handler(
            controller=controller,

            planner=(
                "communication_aware"
            ),
        )

        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        assert (
            result["action"]
            == "KEEP_ROUTE"
        )

        assert (
            result["decision"]["decision"]
            == "KEEP_ROUTE"
        )

        assert (
            controller
            .has_pending_replan
            is False
        )

    asyncio.run(
        scenario()
    )


def test_recovered_before_apply_skips_replan():
    async def scenario():
        controller = (
            make_controller()
        )

        handler = make_handler(
            controller=controller,

            is_degraded=(
                lambda: False
            ),
        )

        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        assert (
            result["action"]
            == "SKIP_RECOVERED"
        )

        assert (
            controller
            .has_pending_replan
            is False
        )

    asyncio.run(
        scenario()
    )


def test_on_event_runs_in_background():
    async def scenario():
        controller = (
            make_controller()
        )

        handler = make_handler(
            controller=controller,
        )

        handler.on_event(
            EVENT.copy()
        )

        await handler.wait_idle()

        assert (
            controller
            .has_pending_replan
            is True
        )

    asyncio.run(
        scenario()
    )


def test_replan_uses_fresh_position():
    async def scenario():
        controller = (
            make_controller()
        )

        handler = make_handler(
            controller=controller,

            get_current_local_position=(
                lambda: (
                    34.6,
                    14.9,
                )
            ),
        )

        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        assert (
            result["incident_grid"]
            == (5, 0)
        )

        assert (
            result["replan_current_grid"]
            == (8, 0)
        )

        assert (
            result["replan_path"][0]
            == (8, 0)
        )

        assert (
            controller
            .has_pending_replan
            is True
        )

        controller.apply_pending_replan()

        first = (
            controller.pop_next()
        )

        assert (
            first["grid_x"],
            first["grid_y"],
        ) == (
            8,
            1,
        )

        assert (
            first["east_m"]
            == 35.0
        )

        assert (
            first["north_m"]
            == 10.0
        )

    asyncio.run(
        scenario()
    )


def test_llm_is_not_in_flight_critical_path():
    async def scenario():
        controller = (
            make_controller()
        )

        handler = make_handler(
            controller=controller,
        )

        # exploding_agent would immediately
        # fail this test if the Handler tried
        # to call the LLM.
        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        assert (
            result["decision_source"]
            == "FAST_POLICY"
        )

        assert (
            result["action"]
            == "REPLAN_QUEUED"
        )

    asyncio.run(
        scenario()
    )


def test_slow_advisor_does_not_block_replan():
    async def scenario():
        import threading

        controller = (
            make_controller()
        )

        advisor_started = (
            threading.Event()
        )

        advisor_release = (
            threading.Event()
        )

        def slow_advisor(
            context,
            fast_decision,
            comparison,
            verbose=False,
        ):
            advisor_started.set()

            advisor_release.wait(
                timeout=1.0
            )

            return {
                "status":
                    "COMPLETED",

                "advisory": {
                    "severity":
                        "WARNING",
                },
            }

        handler = make_handler(
            controller=controller,
            advisor_runner=slow_advisor,
        )

        # This MUST return without waiting
        # for slow_advisor to finish.
        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        assert (
            result["action"]
            == "REPLAN_QUEUED"
        )

        assert (
            controller
            .has_pending_replan
            is True
        )

        assert (
            result["advisor_scheduled"]
            is True
        )

        # Give the background task a chance
        # to enter asyncio.to_thread().
        for _ in range(50):
            if advisor_started.is_set():
                break

            await asyncio.sleep(
                0.01
            )

        assert (
            advisor_started.is_set()
            is True
        )

        # Important proof:
        # route is already pending while
        # Advisor is still blocked.
        assert (
            advisor_release.is_set()
            is False
        )

        advisor_release.set()

        await (
            handler.wait_advisors()
        )

        assert any(
            item.get("action")
            == "ADVISOR_COMPLETED"
            for item in handler.records
        )

    asyncio.run(
        scenario()
    )


def test_advisor_failure_does_not_cancel_replan():
    async def scenario():
        controller = (
            make_controller()
        )

        def failing_advisor(
            context,
            fast_decision,
            comparison,
            verbose=False,
        ):
            raise RuntimeError(
                "simulated advisor failure"
            )

        handler = make_handler(
            controller=controller,
            advisor_runner=(
                failing_advisor
            ),
        )

        result = await (
            handler.process_event(
                EVENT.copy()
            )
        )

        # Flight decision already exists.
        assert (
            result["action"]
            == "REPLAN_QUEUED"
        )

        assert (
            controller
            .has_pending_replan
            is True
        )

        await (
            handler.wait_advisors()
        )

        assert any(
            item.get("action")
            == "ADVISOR_FAILED"
            for item in handler.records
        )

        # Advisor failure must never
        # retract the route replacement.
        assert (
            controller
            .has_pending_replan
            is True
        )

    asyncio.run(
        scenario()
    )
