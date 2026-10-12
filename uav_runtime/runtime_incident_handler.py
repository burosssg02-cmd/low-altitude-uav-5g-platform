import asyncio
import time
from typing import Callable

from agent.realtime_incident_agent import (
    run_realtime_incident_agent,
)

from agent.incident_advisor import (
    run_incident_advisor,
)

from agent.fast_incident_policy import (
    decide_fast_incident_policy,
)
from agent.incident_context import (
    build_incident_context,
)
from communication.radio_map import (
    RadioMap,
)
from planner.coordinate_converter import (
    local_to_gps,
    local_to_grid,
)
from planner.grid_map import (
    GridMap,
    GridNode,
)
from planner.runtime_replanner import (
    build_runtime_replan,
)

from planner.runtime_route_comparison import (
    compare_runtime_routes,
)
from uav_runtime.dynamic_route_controller import (
    DynamicRouteController,
)


DEFAULT_ADVISOR_TIMEOUT_S = 40.0


class RuntimeIncidentHandler:
    """
    Runtime bridge:

    communication event
        -> IncidentContext
        -> Incident Agent
        -> deterministic replanner
        -> validated replacement route
        -> DynamicRouteController

    This class never calls PX4 directly.
    """

    def __init__(
        self,
        *,
        mission_id: str,
        mission_start: GridNode,
        mission_goal: GridNode,
        planner: str,
        altitude_m: float,
        communication_weight: float,
        origin_lat_deg: float,
        origin_lon_deg: float,
        grid_map: GridMap,
        radio_map: RadioMap,
        resolution_m: float,
        route_controller: DynamicRouteController,
        is_degraded: Callable[[], bool] | None = None,
        get_current_local_position: (
            Callable[
                [],
                tuple[float, float] | None,
            ]
            | None
        ) = None,
        advisor_timeout_s: float = DEFAULT_ADVISOR_TIMEOUT_S,
        advisor_runner=run_incident_advisor,
        agent_timeout_s: float = 6.0,
        agent_runner=run_realtime_incident_agent,
    ):
        self.mission_id = mission_id

        self.mission_start = (
            mission_start
        )

        self.mission_goal = (
            mission_goal
        )

        self.planner = planner

        self.altitude_m = altitude_m

        self.communication_weight = (
            communication_weight
        )

        self.origin_lat_deg = (
            origin_lat_deg
        )

        self.origin_lon_deg = (
            origin_lon_deg
        )

        self.grid_map = grid_map
        self.radio_map = radio_map

        self.resolution_m = (
            resolution_m
        )

        self.route_controller = (
            route_controller
        )

        self.is_degraded = (
            is_degraded
            or (lambda: True)
        )

        self.get_current_local_position = (
            get_current_local_position
        )

        self.advisor_timeout_s = float(
            advisor_timeout_s
        )

        if self.advisor_timeout_s <= 0:
            raise ValueError(
                "advisor_timeout_s must be > 0"
            )

        self.advisor_runner = (
            advisor_runner
        )

        # Advisor tasks are deliberately
        # separated from the flight-critical
        # incident task.
        self._advisor_tasks: set[
            asyncio.Task
        ] = set()

        self.agent_timeout_s = float(
            agent_timeout_s
        )

        if self.agent_timeout_s <= 0:
            raise ValueError(
                "agent_timeout_s must be > 0"
            )

        self.agent_runner = (
            agent_runner
        )

        self.records: list[dict] = []

        self._active_task = None

        self.replan_count = 0

    # ==================================================
    # Monitor callback
    # ==================================================

    def on_event(
        self,
        event: dict,
    ) -> None:
        """
        Non-blocking callback for
        RuntimeCommunicationMonitor.

        The monitor must keep sampling while the
        LLM / route analysis runs in the background.
        """

        event_type = event.get(
            "event_type"
        )

        if (
            event_type
            != "COMMUNICATION_DEGRADED"
        ):
            self.records.append(
                {
                    "event_type":
                        event_type,

                    "action":
                        "NO_REPLAN_REQUIRED",
                }
            )

            return

        if (
            self._active_task is not None
            and not self._active_task.done()
        ):
            self.records.append(
                {
                    "event_type":
                        event_type,

                    "action":
                        "INCIDENT_ALREADY_RUNNING",
                }
            )

            return

        self._active_task = (
            asyncio.create_task(
                self.process_event(
                    event.copy()
                )
            )
        )

    # ==================================================
    # Incident processing
    # ==================================================

    async def process_event(
        self,
        event: dict,
    ) -> dict:
        """
        Process one communication degradation event.

        Agent failures do NOT fail the flight.
        Safe fallback is to keep the current route.
        """

        record = {
            "event_type":
                event.get(
                    "event_type"
                ),

            "action":
                "KEEP_ROUTE_ON_ERROR",
        }

        try:
            context = (
                build_incident_context(
                    event=event,

                    mission_id=(
                        self.mission_id
                    ),

                    mission_start=(
                        self.mission_start
                    ),

                    mission_goal=(
                        self.mission_goal
                    ),

                    planner=(
                        self.planner
                    ),

                    altitude_m=(
                        self.altitude_m
                    ),

                    communication_weight=(
                        self.communication_weight
                    ),
                )
            )

            record["context"] = (
                context.to_dict()
            )

            print(
                "[INCIDENT] "
                "Communication degradation "
                "analysis started"
            )

            # ==========================================
            # Flight-critical deterministic decision
            # ==========================================
            #
            # IMPORTANT:
            # MiMo is no longer allowed to block
            # runtime route switching.
            #
            # The remaining route is compared using
            # local deterministic planners + Radio Map,
            # then Fast Incident Policy makes the
            # immediate flight decision.
            # ==========================================

            fast_start = (
                time.perf_counter()
            )

            compare_start = (
                time.perf_counter()
            )

            comparison = await (
                asyncio.to_thread(
                    compare_runtime_routes,

                    grid_map=(
                        self.grid_map
                    ),

                    start=(
                        context.current_grid
                    ),

                    goal=(
                        self.mission_goal
                    ),

                    radio_origin=(
                        self.mission_start
                    ),

                    radio_map=(
                        self.radio_map
                    ),

                    altitude_m=(
                        self.altitude_m
                    ),

                    resolution_m=(
                        self.resolution_m
                    ),

                    communication_weight=(
                        self.communication_weight
                    ),
                )
            )

            compare_latency_s = (
                time.perf_counter()
                - compare_start
            )

            policy_start = (
                time.perf_counter()
            )

            decision = (
                decide_fast_incident_policy(
                    current_planner=(
                        self.planner
                    ),

                    comparison=(
                        comparison
                    ),
                )
            )

            policy_latency_s = (
                time.perf_counter()
                - policy_start
            )

            total_fast_latency_s = (
                time.perf_counter()
                - fast_start
            )

            record["decision"] = (
                decision
            )

            record[
                "decision_source"
            ] = "FAST_POLICY"

            record[
                "compare_latency_s"
            ] = compare_latency_s

            record[
                "policy_latency_s"
            ] = policy_latency_s

            record[
                "fast_decision_latency_s"
            ] = total_fast_latency_s

            print(
                "[INCIDENT] Fast policy: "
                f"{decision['decision']}, "
                f"compare="
                f"{compare_latency_s * 1000:.2f} ms, "
                f"policy="
                f"{policy_latency_s * 1000:.3f} ms, "
                f"total="
                f"{total_fast_latency_s * 1000:.2f} ms"
            )

            # ==========================================
            # Non-blocking MiMo Advisor
            # ==========================================
            #
            # The deterministic decision already exists.
            # Advisor is explanation-only and MUST NOT
            # block or override flight control.
            # ==========================================

            self._schedule_advisor(
                context=context,
                fast_decision=decision,
                comparison=comparison,
            )

            record[
                "advisor_scheduled"
            ] = True

            print(
                "[INCIDENT] Decision: "
                f"{decision['decision']}"
            )

            if (
                decision["decision"]
                != "REPLAN_RECOMMENDED"
            ):
                record["action"] = (
                    "KEEP_ROUTE"
                )

                self.records.append(
                    record
                )

                return record

            if (
                decision[
                    "selected_planner"
                ]
                != "communication_aware"
            ):
                raise RuntimeError(
                    "Replan recommendation "
                    "did not select "
                    "communication_aware"
                )

            # Communication may already have
            # recovered while MiMo was reasoning.
            if not self.is_degraded():
                print(
                    "[INCIDENT] Communication "
                    "already recovered; "
                    "replan skipped"
                )

                record["action"] = (
                    "SKIP_RECOVERED"
                )

                self.records.append(
                    record
                )

                return record

            # ==========================================
            # Refresh UAV position before replanning
            # ==========================================

            replan_current_grid = (
                context.current_grid
            )

            latest_position = None

            if (
                self.get_current_local_position
                is not None
            ):
                latest_position = (
                    self
                    .get_current_local_position()
                )

            if latest_position is not None:
                (
                    latest_east_m,
                    latest_north_m,
                ) = latest_position

                replan_current_grid = (
                    local_to_grid(
                        east_m=(
                            latest_east_m
                        ),

                        north_m=(
                            latest_north_m
                        ),

                        origin_node=(
                            self.mission_start
                        ),

                        resolution_m=(
                            self.resolution_m
                        ),
                    )
                )

                position_drift_m = (
                    (
                        (
                            latest_east_m
                            - context.east_m
                        )
                        ** 2
                        + (
                            latest_north_m
                            - context.north_m
                        )
                        ** 2
                    )
                    ** 0.5
                )

                record[
                    "latest_position"
                ] = {
                    "east_m":
                        latest_east_m,

                    "north_m":
                        latest_north_m,
                }

                record[
                    "decision_position_drift_m"
                ] = position_drift_m

                print(
                    "[INCIDENT] Fresh position: "
                    f"E={latest_east_m:.1f}, "
                    f"N={latest_north_m:.1f}, "
                    f"grid={replan_current_grid}, "
                    f"drift="
                    f"{position_drift_m:.1f} m"
                )

            record[
                "incident_grid"
            ] = context.current_grid

            record[
                "replan_current_grid"
            ] = replan_current_grid

            if (
                replan_current_grid
                == self.mission_goal
            ):
                record["action"] = (
                    "SKIP_ALREADY_AT_GOAL"
                )

                self.records.append(
                    record
                )

                return record

            # ==========================================
            # Deterministic replanning + validation
            # ==========================================

            proposal = (
                build_runtime_replan(
                    grid_map=(
                        self.grid_map
                    ),

                    radio_map=(
                        self.radio_map
                    ),

                    current_grid=(
                        replan_current_grid
                    ),

                    goal=(
                        self.mission_goal
                    ),

                    radio_origin=(
                        self.mission_start
                    ),

                    altitude_m=(
                        self.altitude_m
                    ),

                    resolution_m=(
                        self.resolution_m
                    ),

                    communication_weight=(
                        self.communication_weight
                    ),
                )
            )

            record["replan_path"] = (
                proposal.raw_path
            )

            record["replan_metrics"] = (
                proposal.metrics
            )

            # proposal.waypoints[0] corresponds to
            # current_grid. Do not command the UAV
            # back to the rounded grid centre.
            remaining_waypoints = (
                proposal.waypoints[1:]
            )

            if not remaining_waypoints:
                record["action"] = (
                    "NO_REMAINING_ROUTE"
                )

                self.records.append(
                    record
                )

                return record

            self.replan_count += 1

            gps_waypoints = []

            for index, waypoint in enumerate(
                remaining_waypoints,
                start=1,
            ):
                (
                    latitude_deg,
                    longitude_deg,
                ) = local_to_gps(
                    origin_lat_deg=(
                        self.origin_lat_deg
                    ),

                    origin_lon_deg=(
                        self.origin_lon_deg
                    ),

                    east_m=(
                        waypoint.east_m
                    ),

                    north_m=(
                        waypoint.north_m
                    ),
                )

                gps_waypoints.append(
                    {
                        "index": index,

                        "name": (
                            f"R{self.replan_count}"
                            f"_WP{index}"
                        ),

                        "latitude_deg":
                            latitude_deg,

                        "longitude_deg":
                            longitude_deg,

                        "grid_x":
                            waypoint.grid_node[
                                0
                            ],

                        "grid_y":
                            waypoint.grid_node[
                                1
                            ],

                        "east_m":
                            waypoint.east_m,

                        "north_m":
                            waypoint.north_m,
                    }
                )

            accepted = (
                self.route_controller
                .request_replan(
                    new_waypoints=(
                        gps_waypoints
                    ),

                    reason=(
                        decision["reason"]
                    ),
                )
            )

            record[
                "replacement_waypoints"
            ] = gps_waypoints

            record["accepted"] = (
                accepted
            )

            record["action"] = (
                "REPLAN_QUEUED"
                if accepted
                else "REPLAN_ALREADY_PENDING"
            )

            print(
                "[INCIDENT] Runtime replan "
                f"queued={accepted}, "
                f"waypoints="
                f"{len(gps_waypoints)}"
            )

        except Exception as exc:
            record["error"] = (
                f"{type(exc).__name__}: "
                f"{exc}"
            )

            print(
                "[INCIDENT] ERROR: "
                f"{record['error']}"
            )

        self.records.append(
            record
        )

        return record

    # ==================================================
    # Background Incident Advisor
    # ==================================================

    def _schedule_advisor(
        self,
        *,
        context,
        fast_decision: dict,
        comparison: dict,
    ) -> None:
        """
        Schedule explanation-only MiMo analysis.

        No await occurs here.
        Flight-critical processing continues
        immediately.
        """

        task = asyncio.create_task(
            self._run_advisor_background(
                context=context,
                fast_decision=fast_decision,
                comparison=comparison,
            )
        )

        self._advisor_tasks.add(
            task
        )

        task.add_done_callback(
            self._advisor_tasks.discard
        )

        print(
            "[INCIDENT ADVISOR] "
            "Background analysis scheduled"
        )


    async def _run_advisor_background(
        self,
        *,
        context,
        fast_decision: dict,
        comparison: dict,
    ) -> dict:
        """
        Run MiMo outside the flight event loop.

        Success, failure, or timeout never changes
        the deterministic flight decision.
        """

        started = time.perf_counter()

        try:
            result = await (
                asyncio.wait_for(
                    asyncio.to_thread(
                        self.advisor_runner,
                        context,
                        fast_decision,
                        comparison,
                        False,
                    ),
                    timeout=(
                        self.advisor_timeout_s
                    ),
                )
            )

            status = result.get(
                "status",
                "UNKNOWN",
            )

            if status == "COMPLETED":
                action = (
                    "ADVISOR_COMPLETED"
                )
            else:
                action = (
                    "ADVISOR_FAILED"
                )

        except asyncio.TimeoutError:
            result = {
                "status":
                    "TIMEOUT",

                "error":
                    (
                        "Incident Advisor exceeded "
                        "its background deadline."
                    ),

                "latency_s": (
                    time.perf_counter()
                    - started
                ),
            }

            action = (
                "ADVISOR_TIMEOUT"
            )

        except Exception as exc:
            result = {
                "status":
                    "FAILED",

                "error_type":
                    type(exc).__name__,

                "error":
                    str(exc)[:500],

                "latency_s": (
                    time.perf_counter()
                    - started
                ),
            }

            action = (
                "ADVISOR_FAILED"
            )

        advisor_record = {
            "event_type":
                "INCIDENT_ADVISORY",

            "mission_id":
                self.mission_id,

            "action":
                action,

            "fast_decision":
                fast_decision.get(
                    "decision"
                ),

            "selected_planner":
                fast_decision.get(
                    "selected_planner"
                ),

            "result":
                result,

            "background_latency_s": (
                time.perf_counter()
                - started
            ),
        }

        self.records.append(
            advisor_record
        )

        print(
            "[INCIDENT ADVISOR] "
            f"{action}, "
            f"latency="
            f"{advisor_record['background_latency_s']:.3f}s"
        )

        return result


    async def wait_advisors(
        self,
    ) -> None:
        """
        Optional synchronization helper.

        This is NOT called by the flight-critical
        incident path.

        Tests / shutdown / artifact logging may
        explicitly wait for background advisors.
        """

        while self._advisor_tasks:
            tasks = list(
                self._advisor_tasks
            )

            await asyncio.gather(
                *tasks,
                return_exceptions=True,
            )


    async def wait_idle(
        self,
    ) -> None:
        """
        Used by tests and executor shutdown.
        """

        task = self._active_task

        if task is None:
            return

        try:
            await task

        except asyncio.CancelledError:
            pass
