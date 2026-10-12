import asyncio
import inspect
import time

from datetime import (
    datetime,
    timezone,
)

from communication.degradation_detector import (
    RadioDegradationDetector,
)

from communication.radio_map import (
    RadioMap,
)

from uav_runtime.communication_monitor import (
    CommunicationMonitor,
)


class RuntimeCommunicationMonitor:
    """
    Async runtime communication monitor.

    It listens to PX4 position telemetry,
    evaluates radio quality, and emits
    communication state-change events.
    """

    def __init__(
        self,
        drone,
        origin_lat_deg: float,
        origin_lon_deg: float,
        sample_interval_s: float = 0.2,
        radio_map: RadioMap | None = None,
        detector: RadioDegradationDetector | None = None,
        on_event=None,
    ):
        self.drone = drone

        self.sample_interval_s = (
            sample_interval_s
        )

        self.on_event = on_event

        self.monitor = CommunicationMonitor(
            origin_lat_deg=origin_lat_deg,
            origin_lon_deg=origin_lon_deg,
            radio_map=radio_map,
            detector=detector,
        )

        self._running = False
        self._task = None
        self._last_sample_time = None

        # Monotonic runtime clock used for
        # relative event timing.
        self._started_monotonic = None

    @property
    def state(self) -> str:
        return self.monitor.state

    @property
    def samples(self) -> list[dict]:
        return self.monitor.samples

    @property
    def events(self) -> list[dict]:
        return self.monitor.events

    async def _emit_event(
        self,
        event: dict,
    ):
        if self.on_event is None:
            return

        result = self.on_event(
            event
        )

        if inspect.isawaitable(
            result
        ):
            await result

    async def _watch_positions(
        self,
    ):
        try:
            async for position in (
                self.drone
                .telemetry
                .position()
            ):
                if not self._running:
                    break

                now = time.monotonic()

                if (
                    self._last_sample_time
                    is not None
                    and now
                    - self._last_sample_time
                    < self.sample_interval_s
                ):
                    continue

                self._last_sample_time = (
                    now
                )

                sample = (
                    self.monitor
                    .process_gps_position(
                        latitude_deg=(
                            position.latitude_deg
                        ),
                        longitude_deg=(
                            position.longitude_deg
                        ),
                        relative_altitude_m=(
                            position.relative_altitude_m
                        ),
                    )
                )

                print(
                    "[RADIO] "
                    f"E={sample['east_m']:.1f} m, "
                    f"N={sample['north_m']:.1f} m, "
                    f"RSRP={sample['rsrp_dbm']:.1f} dBm, "
                    f"SINR={sample['sinr_db']:.1f} dB, "
                    f"Score={sample['coverage_score']:.3f}, "
                    f"State={sample['monitor_state']}"
                )

                if (
                    sample["event_type"]
                    is not None
                ):
                    # This object is the same dictionary
                    # stored inside CommunicationMonitor,
                    # so these fields are persisted there
                    # as well.
                    event = (
                        self.monitor.events[-1]
                    )

                    event[
                        "timestamp_utc"
                    ] = (
                        datetime.now(
                            timezone.utc
                        ).isoformat()
                    )

                    if (
                        self._started_monotonic
                        is not None
                    ):
                        event[
                            "elapsed_s"
                        ] = max(
                            0.0,
                            now
                            - self._started_monotonic,
                        )

                    print(
                        "[RADIO EVENT] "
                        f"{event['event_type']} "
                        f"at E={event['east_m']:.1f}, "
                        f"N={event['north_m']:.1f}"
                    )

                    await self._emit_event(
                        event
                    )

        except asyncio.CancelledError:
            pass

        except Exception as exc:
            print(
                "[WARN] Communication monitor "
                f"stopped: {exc}"
            )

    async def start(
        self,
    ):
        if self._running:
            raise RuntimeError(
                "RuntimeCommunicationMonitor "
                "is already running"
            )

        self._running = True
        self._last_sample_time = None

        self._started_monotonic = (
            time.monotonic()
        )

        self._task = asyncio.create_task(
            self._watch_positions()
        )

        print(
            "[RADIO] Runtime communication "
            "monitor started"
        )

    async def stop(
        self,
    ):
        if not self._running:
            return

        self._running = False

        if self._task is not None:
            self._task.cancel()

            await asyncio.gather(
                self._task,
                return_exceptions=True,
            )

        self._task = None

        print(
            "[RADIO] Runtime communication "
            "monitor stopped"
        )

        print(
            f"[RADIO] Samples: "
            f"{len(self.samples)}, "
            f"Events: {len(self.events)}"
        )
