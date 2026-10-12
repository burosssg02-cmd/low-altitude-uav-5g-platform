import asyncio

from planner.coordinate_converter import (
    local_to_gps,
)

from uav_runtime.runtime_communication_monitor import (
    RuntimeCommunicationMonitor,
)


ORIGIN_LAT = 30.0
ORIGIN_LON = 114.0


class FakePosition:
    def __init__(
        self,
        east_m: float,
        north_m: float,
        altitude_m: float = 5.0,
    ):
        lat, lon = local_to_gps(
            origin_lat_deg=ORIGIN_LAT,
            origin_lon_deg=ORIGIN_LON,
            east_m=east_m,
            north_m=north_m,
        )

        self.latitude_deg = lat
        self.longitude_deg = lon
        self.relative_altitude_m = (
            altitude_m
        )


class FakeTelemetry:
    def __init__(
        self,
        positions,
    ):
        self.positions = positions


    async def position(self):
        for position in self.positions:
            yield position
            await asyncio.sleep(0)


class FakeDrone:
    def __init__(
        self,
        positions,
    ):
        self.telemetry = FakeTelemetry(
            positions
        )


def run_monitor(
    positions,
    events_received=None,
):
    async def scenario():
        async def on_event(event):
            if events_received is not None:
                events_received.append(
                    event
                )

        drone = FakeDrone(
            positions
        )

        monitor = (
            RuntimeCommunicationMonitor(
                drone=drone,
                origin_lat_deg=ORIGIN_LAT,
                origin_lon_deg=ORIGIN_LON,
                sample_interval_s=0.0,
                on_event=on_event,
            )
        )

        await monitor.start()

        await asyncio.sleep(
            0.02
        )

        await monitor.stop()

        return monitor

    return asyncio.run(
        scenario()
    )


def test_good_samples_stay_normal():
    positions = [
        FakePosition(0.0, 0.0),
        FakePosition(5.0, 0.0),
        FakePosition(10.0, 0.0),
    ]

    monitor = run_monitor(
        positions
    )

    assert monitor.state == "NORMAL"
    assert len(monitor.samples) == 3
    assert len(monitor.events) == 0


def test_weak_samples_trigger_event():
    positions = [
        FakePosition(25.0, 15.0),
        FakePosition(25.0, 15.0),
        FakePosition(25.0, 15.0),
    ]

    received = []

    monitor = run_monitor(
        positions,
        received,
    )

    assert (
        monitor.state
        == "DEGRADED"
    )

    assert len(monitor.events) == 1
    assert len(received) == 1

    assert (
        received[0]["event_type"]
        == "COMMUNICATION_DEGRADED"
    )


def test_degraded_then_recovers():
    positions = [
        FakePosition(25.0, 15.0),
        FakePosition(25.0, 15.0),
        FakePosition(25.0, 15.0),

        FakePosition(0.0, 0.0),
        FakePosition(0.0, 0.0),
        FakePosition(0.0, 0.0),
    ]

    monitor = run_monitor(
        positions
    )

    assert monitor.state == "NORMAL"

    assert len(monitor.events) == 2

    assert (
        monitor.events[0]["event_type"]
        == "COMMUNICATION_DEGRADED"
    )

    assert (
        monitor.events[1]["event_type"]
        == "COMMUNICATION_RECOVERED"
    )


def test_runtime_events_include_timing_metadata():
    from datetime import datetime

    positions = [
        FakePosition(25.0, 15.0),
        FakePosition(25.0, 15.0),
        FakePosition(25.0, 15.0),

        FakePosition(0.0, 0.0),
        FakePosition(0.0, 0.0),
        FakePosition(0.0, 0.0),
    ]

    monitor = run_monitor(
        positions
    )

    assert len(
        monitor.events
    ) == 2

    degraded = (
        monitor.events[0]
    )

    recovered = (
        monitor.events[1]
    )

    assert (
        degraded["event_type"]
        == "COMMUNICATION_DEGRADED"
    )

    assert (
        recovered["event_type"]
        == "COMMUNICATION_RECOVERED"
    )

    for event in (
        degraded,
        recovered,
    ):
        assert (
            "timestamp_utc"
            in event
        )

        assert (
            "elapsed_s"
            in event
        )

        parsed = (
            datetime.fromisoformat(
                event[
                    "timestamp_utc"
                ]
            )
        )

        assert (
            parsed.tzinfo
            is not None
        )

        assert (
            event["elapsed_s"]
            >= 0.0
        )

    assert (
        recovered["elapsed_s"]
        >= degraded["elapsed_s"]
    )
