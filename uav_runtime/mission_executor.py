import asyncio
import csv
import math
import time

from datetime import datetime, timezone
from pathlib import Path

from agent.incident_advisor import (
    prewarm_incident_rag,
)

from mavsdk import System

from backend.services.mission_service import (
    get_mission_plan,
    update_mission_status,
    GRID_WIDTH,
    GRID_HEIGHT,
    GRID_RESOLUTION_M,
    OBSTACLES,
    RADIO_MAP,
)

from planner.coordinate_converter import local_to_gps

from uav_runtime.telemetry_recorder import (
    TelemetryRecorder,
)

from uav_runtime.runtime_communication_monitor import (
    RuntimeCommunicationMonitor,
)

from uav_runtime.dynamic_route_controller import (
    DynamicRouteController,
)

from uav_runtime.runtime_incident_handler import (
    RuntimeIncidentHandler,
)

from uav_runtime.runtime_artifacts import (
    save_runtime_artifacts,
)

from planner.grid_map import (
    GridMap,
)

from evaluation.run_evaluator import (
    evaluate_run,
)

from evaluation.communication_evaluator import (
    evaluate_communication,
)


POST_FLIGHT_ADVISOR_GRACE_S = 45.0

ARRIVAL_THRESHOLD_M = 1.5
WAYPOINT_TIMEOUT_S = 60.0


def save_planned_waypoints(
    gps_waypoints,
    altitude_m: float,
    output_path: Path,
):
    """
    Save planned mission waypoints for
    trajectory evaluation.
    """

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

        for waypoint in gps_waypoints:
            writer.writerow(
                {
                    "waypoint_id":
                        waypoint["name"],

                    "grid_x":
                        waypoint["grid_x"],

                    "grid_y":
                        waypoint["grid_y"],

                    "east_m":
                        waypoint["east_m"],

                    "north_m":
                        waypoint["north_m"],

                    "latitude_deg":
                        waypoint["latitude_deg"],

                    "longitude_deg":
                        waypoint["longitude_deg"],

                    "relative_altitude_m":
                        altitude_m,
                }
            )

    print(
        f"[EXECUTOR] Planned route: "
        f"{output_path}"
    )


def horizontal_distance_m(
    lat1: float,
    lon1: float,
    lat2: float,
    lon2: float,
) -> float:
    """
    Calculate horizontal distance between
    two GPS coordinates.
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
    Read one PX4 position sample.
    """

    async for position in (
        drone.telemetry.position()
    ):
        return position


async def wait_for_connection(drone):
    """
    Wait until MAVSDK connects to PX4.
    """

    async for state in (
        drone.core.connection_state()
    ):
        if state.is_connected:
            print(
                "[EXECUTOR] Connected to PX4"
            )
            return


async def wait_for_position(drone):
    """
    Wait until PX4 global/home position
    becomes available.
    """

    async for health in (
        drone.telemetry.health()
    ):
        if (
            health.is_global_position_ok
            and health.is_home_position_ok
        ):
            print(
                "[EXECUTOR] Position ready"
            )
            return


async def wait_for_takeoff(
    drone,
    target_altitude_m: float,
):
    """
    Wait for takeoff altitude.
    """

    last_print_time = 0.0

    async for position in (
        drone.telemetry.position()
    ):

        altitude = (
            position.relative_altitude_m
        )

        now = time.monotonic()

        if (
            now - last_print_time
            >= 0.5
        ):
            print(
                f"[EXECUTOR] Altitude: "
                f"{altitude:.2f} m"
            )

            last_print_time = now

        if (
            altitude
            >= target_altitude_m - 0.5
        ):
            print(
                "[EXECUTOR] "
                "Takeoff altitude reached"
            )
            return


async def wait_for_waypoint(
    drone,
    target_lat: float,
    target_lon: float,
    waypoint_name: str,
):
    """
    Wait until UAV reaches waypoint.
    """

    start_time = time.monotonic()
    last_print_time = 0.0

    async for position in (
        drone.telemetry.position()
    ):

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
                f"[EXECUTOR] "
                f"{waypoint_name}: "
                f"{distance:.2f} m remaining"
            )

            last_print_time = now

        if (
            distance
            <= ARRIVAL_THRESHOLD_M
        ):
            print(
                f"[EXECUTOR] "
                f"{waypoint_name} reached"
            )
            return

        if (
            now - start_time
            >= WAYPOINT_TIMEOUT_S
        ):
            raise TimeoutError(
                f"{waypoint_name} timeout"
            )


async def wait_for_waypoint_or_replan(
    drone,
    target_lat: float,
    target_lon: float,
    waypoint_name: str,
    route_controller: DynamicRouteController,
) -> str:
    """
    Wait for either:

    1. the current waypoint to be reached, or
    2. a validated runtime replan to become pending.

    Returns:
        "WAYPOINT_REACHED"
        "REPLAN_PENDING"
    """

    waypoint_task = asyncio.create_task(
        wait_for_waypoint(
            drone=drone,
            target_lat=target_lat,
            target_lon=target_lon,
            waypoint_name=waypoint_name,
        )
    )

    replan_task = asyncio.create_task(
        route_controller
        .replan_event
        .wait()
    )

    done, pending = await asyncio.wait(
        {
            waypoint_task,
            replan_task,
        },
        return_when=(
            asyncio.FIRST_COMPLETED
        ),
    )

    try:
        if (
            replan_task in done
            and route_controller
            .has_pending_replan
        ):
            print(
                "[EXECUTOR] Validated runtime "
                "replan is pending"
            )

            return "REPLAN_PENDING"

        # Propagate waypoint timeout / error.
        await waypoint_task

        return "WAYPOINT_REACHED"

    finally:
        for task in pending:
            task.cancel()

        for task in pending:
            try:
                await task
            except asyncio.CancelledError:
                pass


async def wait_for_landing(drone):
    """
    Wait until PX4 reports landed.
    """

    async for in_air in (
        drone.telemetry.in_air()
    ):
        if not in_air:
            print(
                "[EXECUTOR] Landed"
            )
            return


async def execute_mission(
    mission_id: str,
) -> dict:
    """
    Execute one planned mission through MAVSDK/PX4.

    Flow:
        PLANNED
        -> EXECUTING
        -> LANDING
        -> COMPLETED

    On failure:
        -> FAILED
    """

    mission = get_mission_plan(
        mission_id
    )

    if mission.status not in (
        "PLANNED",
        "EXECUTING",
    ):
        raise RuntimeError(
            f"Mission {mission_id} cannot execute "
            f"from status {mission.status}"
        )

    run_id = (
        datetime.now().strftime(
            "%Y%m%d_%H%M%S"
        )
        + "_"
        + mission_id
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

    drone = System()

    recorder = None
    communication_monitor = None
    route_controller = None
    incident_handler = None

    # Structured record of route replacements that
    # were actually applied by the executor.
    runtime_route_events = []

    airborne = False

    try:
        # ===============================================
        # 0. Prewarm advisory RAG
        # ===============================================
        #
        # RAG is advisory-only. Failure here must not
        # block mission execution or affect Fast Policy.
        #
        print(
            "[EXECUTOR] Prewarming Incident "
            "Advisor RAG..."
        )

        try:
            rag_prewarm_latency_s = (
                await asyncio.to_thread(
                    prewarm_incident_rag
                )
            )

            print(
                "[EXECUTOR] Incident Advisor "
                "RAG ready, "
                f"latency="
                f"{rag_prewarm_latency_s:.3f}s"
            )

        except Exception as rag_exc:
            print(
                "[EXECUTOR] WARNING: RAG "
                "prewarm failed: "
                f"{type(rag_exc).__name__}: "
                f"{rag_exc}"
            )

            print(
                "[EXECUTOR] Mission execution "
                "will continue without blocking."
            )

        # ===============================================
        # 1. Connect PX4
        # ===============================================

        print(
            f"[EXECUTOR] Mission: "
            f"{mission_id}"
        )

        print(
            "[EXECUTOR] Connecting to PX4..."
        )

        await drone.connect(
            system_address=(
                "udpin://0.0.0.0:14540"
            )
        )

        await wait_for_connection(
            drone
        )

        await wait_for_position(
            drone
        )

        # ===============================================
        # 2. Read current home position
        # ===============================================

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
            f"[EXECUTOR] Home: "
            f"{home_lat:.7f}, "
            f"{home_lon:.7f}"
        )

        # ===============================================
        # 3. Convert local waypoints to GPS
        # ===============================================

        gps_waypoints = []

        for waypoint in mission.waypoints:

            latitude_deg, longitude_deg = (
                local_to_gps(
                    origin_lat_deg=home_lat,
                    origin_lon_deg=home_lon,
                    east_m=waypoint.east_m,
                    north_m=waypoint.north_m,
                )
            )

            gps_waypoints.append(
                {
                    "index":
                        waypoint.index,

                    "name":
                        f"WP{waypoint.index}",

                    "latitude_deg":
                        latitude_deg,

                    "longitude_deg":
                        longitude_deg,

                    "grid_x":
                        waypoint.grid_x,

                    "grid_y":
                        waypoint.grid_y,

                    "east_m":
                        waypoint.east_m,

                    "north_m":
                        waypoint.north_m,
                }
            )

        # ===============================================
        # Runtime mutable remaining route
        # ===============================================

        # WP0 is the current takeoff/start point.
        # Only future waypoints belong to the
        # runtime route controller.
        route_controller = (
            DynamicRouteController(
                gps_waypoints[1:]
            )
        )

        print(
            "[EXECUTOR] Dynamic route controller "
            f"initialized with "
            f"{route_controller.remaining_count} "
            "remaining waypoints"
        )

        # ===============================================
        # 4. Save planned route
        # ===============================================

        save_planned_waypoints(
            gps_waypoints=gps_waypoints,
            altitude_m=mission.altitude_m,
            output_path=planned_waypoints_csv,
        )

        # ===============================================
        # 5. Create recorder
        # ===============================================

        recorder = TelemetryRecorder(
            drone=drone,
            origin_lat_deg=home_lat,
            origin_lon_deg=home_lon,
            sample_interval_s=0.2,
        )

        recorder.set_target_waypoint(
            "TAKEOFF"
        )

        await recorder.start()

        # ===============================================
        # Runtime communication monitoring
        # ===============================================

        runtime_grid_map = GridMap(
            width=GRID_WIDTH,
            height=GRID_HEIGHT,
            obstacles=OBSTACLES,
        )

        incident_handler = (
            RuntimeIncidentHandler(
                mission_id=mission_id,

                mission_start=(
                    mission.start
                ),

                mission_goal=(
                    mission.goal
                ),

                planner=(
                    mission.planner
                ),

                altitude_m=(
                    mission.altitude_m
                ),

                communication_weight=(
                    mission.communication_weight
                ),

                origin_lat_deg=(
                    home_lat
                ),

                origin_lon_deg=(
                    home_lon
                ),

                grid_map=(
                    runtime_grid_map
                ),

                radio_map=(
                    RADIO_MAP
                ),

                resolution_m=(
                    GRID_RESOLUTION_M
                ),

                route_controller=(
                    route_controller
                ),

                # This lambda is evaluated later,
                # after communication_monitor exists.
                is_degraded=lambda: (
                    communication_monitor
                    is not None
                    and communication_monitor.state
                    == "DEGRADED"
                ),

                get_current_local_position=lambda: (
                    (
                        communication_monitor
                        .samples[-1]["east_m"],

                        communication_monitor
                        .samples[-1]["north_m"],
                    )

                    if (
                        communication_monitor
                        is not None
                        and communication_monitor.samples
                    )

                    else None
                ),
            )
        )

        communication_monitor = (
            RuntimeCommunicationMonitor(
                drone=drone,
                origin_lat_deg=home_lat,
                origin_lon_deg=home_lon,
                sample_interval_s=0.2,
                on_event=(
                    incident_handler.on_event
                ),
            )
        )

        await communication_monitor.start()

        print(
            "[EXECUTOR] Runtime communication "
            "monitor enabled"
        )

        # ===============================================
        # 5. Update mission state
        # ===============================================

        if mission.status == "PLANNED":
            update_mission_status(
                mission_id,
                "EXECUTING",
            )

        # ===============================================
        # 6. Takeoff
        # ===============================================

        altitude_m = (
            mission.altitude_m
        )

        await drone.action.set_takeoff_altitude(
            altitude_m
        )

        print(
            "[EXECUTOR] Arming..."
        )

        await drone.action.arm()

        airborne = True

        print(
            "[EXECUTOR] Taking off..."
        )

        await drone.action.takeoff()

        await wait_for_takeoff(
            drone,
            altitude_m,
        )

        target_absolute_altitude = (
            home_absolute_altitude
            + altitude_m
        )

        # ===============================================
        # 7. Execute waypoints
        # ===============================================

        # Remaining route is now mutable.
        # A validated runtime replan can replace
        # all not-yet-executed waypoints.

        while True:

            # Apply a validated replacement route
            # before choosing the next waypoint.
            if (
                route_controller
                .has_pending_replan
            ):
                metadata = (
                    route_controller
                    .apply_pending_replan()
                )

                runtime_route_events.append(
                    {
                        "event_type":
                            "RUNTIME_ROUTE_REPLACEMENT_APPLIED",

                        "timestamp_utc":
                            datetime.now(
                                timezone.utc
                            ).isoformat(),

                        "metadata":
                            metadata,
                    }
                )

                print(
                    "[EXECUTOR] Runtime route "
                    "replacement applied: "
                    f"{metadata}"
                )

            waypoint = (
                route_controller.pop_next()
            )

            if waypoint is None:
                break

            waypoint_name = (
                waypoint["name"]
            )

            recorder.set_target_waypoint(
                waypoint_name
            )

            print(
                f"[EXECUTOR] Flying to "
                f"{waypoint_name}"
            )

            await drone.action.goto_location(
                waypoint["latitude_deg"],
                waypoint["longitude_deg"],
                target_absolute_altitude,
                0.0,
            )

            wait_result = (
                await wait_for_waypoint_or_replan(
                    drone=drone,
                    target_lat=(
                        waypoint[
                            "latitude_deg"
                        ]
                    ),
                    target_lon=(
                        waypoint[
                            "longitude_deg"
                        ]
                    ),
                    waypoint_name=(
                        waypoint_name
                    ),
                    route_controller=(
                        route_controller
                    ),
                )
            )

            if (
                wait_result
                == "REPLAN_PENDING"
            ):
                print(
                    "[EXECUTOR] Current waypoint "
                    "superseded by runtime replan"
                )

                # No sleep here. On the next loop,
                # apply_pending_replan() replaces
                # all remaining waypoints.
                continue

            await asyncio.sleep(
                2
            )

        # ===============================================
        # 8. Landing
        # ===============================================

        update_mission_status(
            mission_id,
            "LANDING",
        )

        recorder.set_target_waypoint(
            "LANDING"
        )

        print(
            "[EXECUTOR] Landing..."
        )

        await drone.action.land()

        await wait_for_landing(
            drone
        )

        airborne = False

        recorder.set_target_waypoint(
            "LANDED"
        )

        # Let telemetry background tasks receive
        # final landed state.
        await asyncio.sleep(
            1.5
        )

        # ===============================================
        # 9. Complete mission
        # ===============================================

        update_mission_status(
            mission_id,
            "COMPLETED",
        )

        print(
            f"[EXECUTOR] Mission "
            f"{mission_id} completed"
        )

        return {
            "mission_id":
                mission_id,

            "status":
                "COMPLETED",

            "run_id":
                run_id,

            "run_dir":
                str(run_dir),
        }

    except Exception as exc:

        error_message = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        print(
            f"[EXECUTOR] ERROR: "
            f"{error_message}"
        )

        # Safety landing attempt
        if airborne:

            try:
                if recorder is not None:
                    recorder.set_target_waypoint(
                        "EMERGENCY_LANDING"
                    )

                print(
                    "[EXECUTOR] "
                    "Requesting emergency landing..."
                )

                await drone.action.land()

                await wait_for_landing(
                    drone
                )

                airborne = False

                if recorder is not None:
                    recorder.set_target_waypoint(
                        "LANDED"
                    )

                    await asyncio.sleep(
                        1.5
                    )

            except Exception as landing_exc:

                print(
                    "[EXECUTOR] "
                    f"Emergency landing failed: "
                    f"{landing_exc}"
                )

        update_mission_status(
            mission_id,
            "FAILED",
            error_message=error_message,
        )

        raise

    finally:

        # ===============================================
        # 10. Stop recorder and save telemetry
        # ===============================================

        if communication_monitor is not None:
            try:
                await communication_monitor.stop()

            except Exception as monitor_exc:
                print(
                    "[EXECUTOR] Runtime communication "
                    "monitor stop failed: "
                    f"{type(monitor_exc).__name__}: "
                    f"{monitor_exc}"
                )

        # ===============================================
        # Runtime incident / replan artifacts
        # ===============================================

        if incident_handler is not None:

            # Flight is already finished at this point.
            # Waiting here cannot delay a flight-critical
            # replan or landing command.
            try:
                await asyncio.wait_for(
                    incident_handler.wait_advisors(),
                    # Flight is already finished.
                    # Allow the background Advisor enough
                    # time to finish so its result can be
                    # included in runtime artifacts.
                    timeout=POST_FLIGHT_ADVISOR_GRACE_S,
                )

            except asyncio.TimeoutError:
                print(
                    "[ARTIFACT] Advisor still pending "
                    "after post-flight grace period"
                )

            except Exception as advisor_wait_exc:
                print(
                    "[ARTIFACT] Advisor wait failed: "
                    f"{type(advisor_wait_exc).__name__}: "
                    f"{advisor_wait_exc}"
                )

        try:
            save_runtime_artifacts(
                run_dir=run_dir,

                mission_id=mission_id,

                mission_metadata={
                    "planner":
                        mission.planner,

                    "start":
                        mission.start,

                    "goal":
                        mission.goal,

                    "altitude_m":
                        mission.altitude_m,

                    "communication_weight":
                        mission.communication_weight,
                },

                incident_handler=(
                    incident_handler
                ),

                communication_monitor=(
                    communication_monitor
                ),

                route_events=(
                    runtime_route_events
                ),
            )

        except Exception as artifact_exc:
            print(
                "[ARTIFACT] Runtime artifact "
                "save failed: "
                f"{type(artifact_exc).__name__}: "
                f"{artifact_exc}"
            )

        if recorder is not None:

            await recorder.stop()

            recorder.save_csv(
                actual_trajectory_csv
            )

            print(
                f"[EXECUTOR] Trajectory: "
                f"{actual_trajectory_csv}"
            )

            if (
                planned_waypoints_csv.exists()
                and actual_trajectory_csv.exists()
            ):
                try:
                    metrics = evaluate_run(
                        run_dir
                    )

                    print(
                        "[EXECUTOR] Evaluation completed"
                    )

                    print(
                        f"[EXECUTOR] "
                        f"Planned distance: "
                        f"{metrics['planned_distance_m']:.2f} m"
                    )

                    print(
                        f"[EXECUTOR] "
                        f"Actual distance: "
                        f"{metrics['actual_distance_m']:.2f} m"
                    )

                    print(
                        f"[EXECUTOR] "
                        f"Flight efficiency: "
                        f"{metrics['flight_efficiency'] * 100:.2f}%"
                    )

                except Exception as evaluation_exc:
                    print(
                        "[EXECUTOR] "
                        "Evaluation failed: "
                        f"{type(evaluation_exc).__name__}: "
                        f"{evaluation_exc}"
                    )

        # ===============================================
        # 11. Communication evaluation
        # ===============================================

        if actual_trajectory_csv.exists():
            try:
                communication_summary = (
                    evaluate_communication(
                        run_dir
                    )
                )

                print(
                    "[EXECUTOR] "
                    "Communication evaluation completed"
                )

                print(
                    f"[EXECUTOR] Mean RSRP: "
                    f"{communication_summary['mean_rsrp_dbm']:.2f} dBm"
                )

                print(
                    f"[EXECUTOR] Min RSRP: "
                    f"{communication_summary['min_rsrp_dbm']:.2f} dBm"
                )

                print(
                    f"[EXECUTOR] Mean SINR: "
                    f"{communication_summary['mean_sinr_db']:.2f} dB"
                )

                print(
                    f"[EXECUTOR] Min SINR: "
                    f"{communication_summary['min_sinr_db']:.2f} dB"
                )

                print(
                    f"[EXECUTOR] Mean coverage score: "
                    f"{communication_summary['mean_coverage_score']:.3f}"
                )

                print(
                    f"[EXECUTOR] Min coverage score: "
                    f"{communication_summary['min_coverage_score']:.3f}"
                )

                print(
                    f"[EXECUTOR] Handovers: "
                    f"{communication_summary['handover_count']}"
                )

            except Exception as communication_exc:
                print(
                    "[EXECUTOR] "
                    "Communication evaluation failed: "
                    f"{type(communication_exc).__name__}: "
                    f"{communication_exc}"
                )

        # ===============================================
        # V0.7.8-B4 automatic dynamic replan evaluation
        # ===============================================
        #
        # This runs near the end of the existing finally
        # block, after trajectory, communication and
        # runtime artifacts have already been persisted.
        #
        # Evaluation failure must never retroactively
        # change a successfully completed flight status.
        try:
            from evaluation.dynamic_replan_evaluator import (
                evaluate_dynamic_replan_if_available,
            )
    
            dynamic_summary = (
                evaluate_dynamic_replan_if_available(
                    run_dir
                )
            )
    
            if dynamic_summary is not None:
                print(
                    "[EXECUTOR] Dynamic replan "
                    "evaluation completed"
                )
    
                distance_eval = (
                    dynamic_summary[
                        "distance_evaluation"
                    ]
                )
    
                print(
                    "[EXECUTOR] Revised planned "
                    "distance: "
                    f"{distance_eval['revised_total_planned_distance_m']:.2f} m"
                )
    
                print(
                    "[EXECUTOR] Dynamic flight "
                    "efficiency: "
                    f"{distance_eval['dynamic_flight_efficiency'] * 100:.2f}%"
                )
    
                print(
                    "[EXECUTOR] Dynamic extra "
                    "distance: "
                    f"{distance_eval['dynamic_extra_distance_m']:.2f} m"
                )
    
            else:
                print(
                    "[EXECUTOR] No applied runtime "
                    "replan; dynamic evaluation skipped"
                )
    
        except Exception as dynamic_evaluation_exc:
            print(
                "[EXECUTOR] Dynamic replan "
                "evaluation failed: "
                f"{type(dynamic_evaluation_exc).__name__}: "
                f"{dynamic_evaluation_exc}"
            )


        # ===============================================
        # V0.7.8-B5 automatic multi-replan evaluation
        # ===============================================
        #
        # Single-replan evaluation remains available
        # through B4. When two or more runtime replans
        # were actually applied, this additional
        # evaluator builds episode-level and mission-
        # level multi-replan metrics.
        #
        # Evaluation failure must never change the
        # mission execution result.
        try:
            from evaluation.multi_replan_evaluator import (
                evaluate_multi_replan_if_available,
            )

            multi_replan_summary = (
                evaluate_multi_replan_if_available(
                    run_dir
                )
            )

            if multi_replan_summary is not None:
                multi_overall = (
                    multi_replan_summary[
                        "overall"
                    ]
                )

                print(
                    "[EXECUTOR] Multi-replan "
                    "evaluation completed"
                )

                print(
                    "[EXECUTOR] Multi-replan "
                    "episodes: "
                    f"{multi_replan_summary['episode_count']}"
                )

                print(
                    "[EXECUTOR] Multi-replan revised "
                    "planned distance: "
                    f"{multi_overall['revised_total_planned_distance_m']:.2f} m"
                )

                multi_efficiency = (
                    multi_overall[
                        "dynamic_flight_efficiency"
                    ]
                )

                if multi_efficiency is not None:
                    print(
                        "[EXECUTOR] Multi-replan "
                        "dynamic flight efficiency: "
                        f"{multi_efficiency * 100:.2f}%"
                    )

                print(
                    "[EXECUTOR] Multi-replan dynamic "
                    "extra distance: "
                    f"{multi_overall['dynamic_extra_distance_m']:.2f} m"
                )

            else:
                print(
                    "[EXECUTOR] Fewer than two "
                    "applied runtime replans; "
                    "multi-replan evaluation skipped"
                )

        except Exception as multi_replan_exc:
            print(
                "[EXECUTOR] Multi-replan "
                "evaluation failed: "
                f"{type(multi_replan_exc).__name__}: "
                f"{multi_replan_exc}"
            )


        # ===============================================
        # V0.8-B3 automatic RAG / Advisor evaluation
        # ===============================================
        #
        # Runtime artifacts have already been persisted
        # at this point. This evaluator is post-flight
        # only and has no flight-control authority.
        #
        # Evaluation failure must never change mission
        # execution status.
        try:
            from evaluation.rag_advisor_evaluator import (
                evaluate_rag_advisor_if_available,
            )

            rag_advisor_summary = (
                evaluate_rag_advisor_if_available(
                    run_dir
                )
            )

            if rag_advisor_summary is not None:
                print(
                    "[EXECUTOR] RAG / Advisor "
                    "evaluation completed"
                )

                print(
                    "[EXECUTOR] Advisor records: "
                    f"{rag_advisor_summary['advisor_record_count']}"
                )

                success_rate = (
                    rag_advisor_summary.get(
                        "advisor_success_rate"
                    )
                )

                if success_rate is not None:
                    print(
                        "[EXECUTOR] Advisor success "
                        "rate: "
                        f"{success_rate * 100:.2f}%"
                    )

                rag_usage_rate = (
                    rag_advisor_summary
                    .get(
                        "rag",
                        {},
                    )
                    .get(
                        "usage_rate"
                    )
                )

                if rag_usage_rate is not None:
                    print(
                        "[EXECUTOR] RAG usage rate: "
                        f"{rag_usage_rate * 100:.2f}%"
                    )

                rag_latency_mean = (
                    rag_advisor_summary
                    .get(
                        "rag",
                        {},
                    )
                    .get(
                        "retrieval_latency",
                        {},
                    )
                    .get(
                        "mean_s"
                    )
                )

                if rag_latency_mean is not None:
                    print(
                        "[EXECUTOR] Mean RAG "
                        "retrieval latency: "
                        f"{rag_latency_mean:.3f}s"
                    )

                safety = (
                    rag_advisor_summary.get(
                        "safety_consistency",
                        {},
                    )
                )

                fast_match_rate = (
                    safety.get(
                        "fast_decision_match_rate"
                    )
                )

                if fast_match_rate is not None:
                    print(
                        "[EXECUTOR] Fast decision "
                        "consistency: "
                        f"{fast_match_rate * 100:.2f}%"
                    )

                planner_match_rate = (
                    safety.get(
                        "selected_planner_match_rate"
                    )
                )

                if planner_match_rate is not None:
                    print(
                        "[EXECUTOR] Planner "
                        "consistency: "
                        f"{planner_match_rate * 100:.2f}%"
                    )

                print(
                    "[EXECUTOR] RAG / Advisor "
                    "artifact: "
                    f"{run_dir / 'rag_advisor_evaluation.json'}"
                )

            else:
                print(
                    "[EXECUTOR] No persisted "
                    "Incident Advisor records; "
                    "RAG / Advisor evaluation skipped"
                )

        except Exception as rag_advisor_eval_exc:
            print(
                "[EXECUTOR] RAG / Advisor "
                "evaluation failed: "
                f"{type(rag_advisor_eval_exc).__name__}: "
                f"{rag_advisor_eval_exc}"
            )

