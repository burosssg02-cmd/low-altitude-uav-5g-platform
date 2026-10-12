from communication.radio_map import (
    build_demo_radio_map,
)

from planner.coordinate_converter import (
    local_to_gps,
)

from uav_runtime.communication_monitor import (
    CommunicationMonitor,
)


ORIGIN_LAT = 30.0
ORIGIN_LON = 114.0


def build_monitor():
    return CommunicationMonitor(
        origin_lat_deg=ORIGIN_LAT,
        origin_lon_deg=ORIGIN_LON,
        radio_map=build_demo_radio_map(),
    )


def test_good_position_stays_normal():
    monitor = build_monitor()

    sample = (
        monitor.process_local_position(
            east_m=0.0,
            north_m=0.0,
            altitude_m=5.0,
        )
    )

    assert (
        sample["monitor_state"]
        == "NORMAL"
    )

    assert sample["event_type"] is None

    assert sample["rsrp_dbm"] > -95.0

    assert (
        sample["coverage_score"]
        > 0.55
    )


def test_weak_zone_triggers_degradation():
    monitor = build_monitor()

    sample = None

    for _ in range(3):
        sample = (
            monitor.process_local_position(
                east_m=25.0,
                north_m=15.0,
                altitude_m=5.0,
            )
        )

    assert sample is not None

    assert (
        sample["event_type"]
        == "COMMUNICATION_DEGRADED"
    )

    assert (
        monitor.state
        == "DEGRADED"
    )

    assert len(monitor.events) == 1

    assert (
        monitor.events[0][
            "event_type"
        ]
        == "COMMUNICATION_DEGRADED"
    )


def test_recovery_event():
    monitor = build_monitor()

    for _ in range(3):
        monitor.process_local_position(
            east_m=25.0,
            north_m=15.0,
            altitude_m=5.0,
        )

    assert (
        monitor.state
        == "DEGRADED"
    )

    sample = None

    for _ in range(3):
        sample = (
            monitor.process_local_position(
                east_m=0.0,
                north_m=0.0,
                altitude_m=5.0,
            )
        )

    assert sample is not None

    assert (
        sample["event_type"]
        == "COMMUNICATION_RECOVERED"
    )

    assert (
        monitor.state
        == "NORMAL"
    )

    assert len(monitor.events) == 2


def test_gps_position_conversion():
    monitor = build_monitor()

    latitude_deg, longitude_deg = (
        local_to_gps(
            origin_lat_deg=ORIGIN_LAT,
            origin_lon_deg=ORIGIN_LON,
            east_m=25.0,
            north_m=15.0,
        )
    )

    sample = (
        monitor.process_gps_position(
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            relative_altitude_m=5.0,
        )
    )

    assert (
        abs(
            sample["east_m"]
            - 25.0
        )
        < 0.05
    )

    assert (
        abs(
            sample["north_m"]
            - 15.0
        )
        < 0.05
    )

    assert (
        sample["rsrp_dbm"]
        < -95.0
    )


def test_communication_aware_like_position_is_normal():
    monitor = build_monitor()

    sample = None

    for _ in range(5):
        sample = (
            monitor.process_local_position(
                east_m=20.0,
                north_m=-20.0,
                altitude_m=5.0,
            )
        )

    assert sample is not None

    assert (
        monitor.state
        == "NORMAL"
    )

    assert sample["event_type"] is None
