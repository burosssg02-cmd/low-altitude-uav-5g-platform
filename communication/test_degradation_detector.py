from communication.degradation_detector import (
    RadioDegradationDetector,
)


def test_single_bad_sample_does_not_trigger():
    detector = (
        RadioDegradationDetector()
    )

    event = detector.update(
        rsrp_dbm=-100.0,
        sinr_db=-1.0,
        coverage_score=0.45,
    )

    assert event is None
    assert detector.state == "NORMAL"


def test_three_bad_samples_trigger_degradation():
    detector = (
        RadioDegradationDetector()
    )

    event = None

    for _ in range(3):
        event = detector.update(
            rsrp_dbm=-100.0,
            sinr_db=-1.0,
            coverage_score=0.45,
        )

    assert event is not None

    assert (
        event["event_type"]
        == "COMMUNICATION_DEGRADED"
    )

    assert detector.state == "DEGRADED"


def test_three_good_samples_recover():
    detector = (
        RadioDegradationDetector()
    )

    for _ in range(3):
        detector.update(
            rsrp_dbm=-100.0,
            sinr_db=-1.0,
            coverage_score=0.45,
        )

    assert detector.state == "DEGRADED"

    event = None

    for _ in range(3):
        event = detector.update(
            rsrp_dbm=-80.0,
            sinr_db=8.0,
            coverage_score=0.80,
        )

    assert event is not None

    assert (
        event["event_type"]
        == "COMMUNICATION_RECOVERED"
    )

    assert detector.state == "NORMAL"


def test_comm_aware_like_samples_do_not_trigger():
    detector = (
        RadioDegradationDetector()
    )

    samples = [
        (-76.0, 8.0, 0.84),
        (-79.0, 3.0, 0.76),
        (-80.1, 1.7, 0.755),
        (-77.0, 6.0, 0.82),
    ]

    for (
        rsrp,
        sinr,
        score,
    ) in samples:

        event = detector.update(
            rsrp_dbm=rsrp,
            sinr_db=sinr,
            coverage_score=score,
        )

        assert event is None

    assert detector.state == "NORMAL"


def test_realistic_post_weak_zone_recovery():
    detector = (
        RadioDegradationDetector()
    )

    # Enter degraded state.
    for _ in range(3):
        detector.update(
            rsrp_dbm=-98.0,
            sinr_db=0.0,
            coverage_score=0.48,
        )

    assert detector.state == "DEGRADED"

    # Values similar to the actual flight after
    # leaving the weak-coverage region.
    recovery_samples = [
        (-79.9, 1.1, 0.747),
        (-79.9, 1.2, 0.749),
        (-79.8, 1.3, 0.750),
    ]

    event = None

    for rsrp, sinr, score in recovery_samples:
        event = detector.update(
            rsrp_dbm=rsrp,
            sinr_db=sinr,
            coverage_score=score,
        )

    assert event is not None

    assert (
        event["event_type"]
        == "COMMUNICATION_RECOVERED"
    )

    assert detector.state == "NORMAL"
