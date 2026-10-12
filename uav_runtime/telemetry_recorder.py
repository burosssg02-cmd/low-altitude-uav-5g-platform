import asyncio
import csv
import math
import time

from datetime import datetime, timezone
from pathlib import Path

from planner.coordinate_converter import gps_to_local


class TelemetryRecorder:
    """
    Record PX4 telemetry data during a UAV mission.

    Responsibilities:
        1. Read PX4 position telemetry
        2. Read velocity / flight mode / in-air state
        3. Convert GPS position to local East/North coordinates
        4. Store trajectory samples in memory
        5. Export trajectory to CSV
    """

    FIELDNAMES = [
        "sample_index",
        "timestamp_utc",
        "elapsed_s",
        "latitude_deg",
        "longitude_deg",
        "absolute_altitude_m",
        "relative_altitude_m",
        "east_m",
        "north_m",
        "velocity_north_m_s",
        "velocity_east_m_s",
        "velocity_down_m_s",
        "horizontal_speed_m_s",
        "total_speed_m_s",
        "in_air",
        "flight_mode",
        "target_waypoint",
    ]

    def __init__(
        self,
        drone,
        origin_lat_deg: float,
        origin_lon_deg: float,
        sample_interval_s: float = 0.2,
    ):
        self.drone = drone

        self.origin_lat_deg = origin_lat_deg
        self.origin_lon_deg = origin_lon_deg

        self.sample_interval_s = sample_interval_s

        self.records = []

        self.target_waypoint = "NONE"

        self.velocity_north_m_s = 0.0
        self.velocity_east_m_s = 0.0
        self.velocity_down_m_s = 0.0

        self.in_air = False
        self.flight_mode = "UNKNOWN"

        self._start_time = None
        self._last_record_time = None

        self._tasks = []
        self._running = False

    def set_target_waypoint(
        self,
        waypoint_name: str,
    ):
        """
        Update the waypoint currently being executed.
        """

        self.target_waypoint = waypoint_name

    async def _watch_velocity(self):
        try:
            async for velocity in self.drone.telemetry.velocity_ned():

                if not self._running:
                    break

                self.velocity_north_m_s = (
                    velocity.north_m_s
                )

                self.velocity_east_m_s = (
                    velocity.east_m_s
                )

                self.velocity_down_m_s = (
                    velocity.down_m_s
                )

        except asyncio.CancelledError:
            pass

        except Exception as exc:
            print(
                f"[WARN] Velocity telemetry stopped: "
                f"{exc}"
            )

    async def _watch_flight_mode(self):
        try:
            async for mode in self.drone.telemetry.flight_mode():

                if not self._running:
                    break

                self.flight_mode = getattr(
                    mode,
                    "name",
                    str(mode),
                )

        except asyncio.CancelledError:
            pass

        except Exception as exc:
            print(
                f"[WARN] Flight-mode telemetry stopped: "
                f"{exc}"
            )

    async def _watch_in_air(self):
        try:
            async for in_air in self.drone.telemetry.in_air():

                if not self._running:
                    break

                self.in_air = bool(in_air)

        except asyncio.CancelledError:
            pass

        except Exception as exc:
            print(
                f"[WARN] In-air telemetry stopped: "
                f"{exc}"
            )

    async def _record_positions(self):
        try:
            async for position in self.drone.telemetry.position():

                if not self._running:
                    break

                current_time = time.monotonic()

                if (
                    self._last_record_time is not None
                    and current_time
                    - self._last_record_time
                    < self.sample_interval_s
                ):
                    continue

                self._last_record_time = current_time

                elapsed_s = (
                    current_time
                    - self._start_time
                )

                east_m, north_m = gps_to_local(
                    origin_lat_deg=self.origin_lat_deg,
                    origin_lon_deg=self.origin_lon_deg,
                    latitude_deg=position.latitude_deg,
                    longitude_deg=position.longitude_deg,
                )

                horizontal_speed_m_s = math.sqrt(
                    self.velocity_north_m_s ** 2
                    + self.velocity_east_m_s ** 2
                )

                total_speed_m_s = math.sqrt(
                    self.velocity_north_m_s ** 2
                    + self.velocity_east_m_s ** 2
                    + self.velocity_down_m_s ** 2
                )

                record = {
                    "sample_index": len(self.records),
                    "timestamp_utc": datetime.now(
                        timezone.utc
                    ).isoformat(),
                    "elapsed_s": elapsed_s,
                    "latitude_deg": position.latitude_deg,
                    "longitude_deg": position.longitude_deg,
                    "absolute_altitude_m": (
                        position.absolute_altitude_m
                    ),
                    "relative_altitude_m": (
                        position.relative_altitude_m
                    ),
                    "east_m": east_m,
                    "north_m": north_m,
                    "velocity_north_m_s": (
                        self.velocity_north_m_s
                    ),
                    "velocity_east_m_s": (
                        self.velocity_east_m_s
                    ),
                    "velocity_down_m_s": (
                        self.velocity_down_m_s
                    ),
                    "horizontal_speed_m_s": (
                        horizontal_speed_m_s
                    ),
                    "total_speed_m_s": (
                        total_speed_m_s
                    ),
                    "in_air": self.in_air,
                    "flight_mode": self.flight_mode,
                    "target_waypoint": (
                        self.target_waypoint
                    ),
                }

                self.records.append(record)

        except asyncio.CancelledError:
            pass

        except Exception as exc:
            print(
                f"[WARN] Position recorder stopped: "
                f"{exc}"
            )

    async def start(self):
        """
        Start telemetry recording in background tasks.
        """

        if self._running:
            raise RuntimeError(
                "TelemetryRecorder is already running"
            )

        self.records = []

        self._running = True

        self._start_time = time.monotonic()
        self._last_record_time = None

        self._tasks = [
            asyncio.create_task(
                self._watch_velocity()
            ),
            asyncio.create_task(
                self._watch_flight_mode()
            ),
            asyncio.create_task(
                self._watch_in_air()
            ),
            asyncio.create_task(
                self._record_positions()
            ),
        ]

        print(
            "[RECORDER] Telemetry recording started"
        )

    async def stop(self):
        """
        Stop all telemetry recording tasks.
        """

        if not self._running:
            return

        self._running = False

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(
            *self._tasks,
            return_exceptions=True,
        )

        self._tasks = []

        print(
            "[RECORDER] Telemetry recording stopped"
        )

        print(
            f"[RECORDER] Samples collected: "
            f"{len(self.records)}"
        )

    def save_csv(
        self,
        output_path,
    ):
        """
        Save all trajectory samples to CSV.
        """

        output_path = Path(output_path)

        output_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        with output_path.open(
            "w",
            newline="",
            encoding="utf-8",
        ) as file:

            writer = csv.DictWriter(
                file,
                fieldnames=self.FIELDNAMES,
            )

            writer.writeheader()

            writer.writerows(
                self.records
            )

        print(
            f"[RECORDER] CSV saved: "
            f"{output_path}"
        )
