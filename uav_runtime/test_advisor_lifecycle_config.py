from agent.incident_advisor import (
    ADVISOR_REQUEST_TIMEOUT_S,
)

from uav_runtime.runtime_incident_handler import (
    DEFAULT_ADVISOR_TIMEOUT_S,
)

from uav_runtime.mission_executor import (
    POST_FLIGHT_ADVISOR_GRACE_S,
)


def test_advisor_lifecycle_deadlines_are_ordered():
    assert (
        ADVISOR_REQUEST_TIMEOUT_S
        == 20.0
    )

    assert (
        DEFAULT_ADVISOR_TIMEOUT_S
        == 40.0
    )

    assert (
        POST_FLIGHT_ADVISOR_GRACE_S
        == 45.0
    )

    # HTTP/network handling sits inside the
    # overall background Advisor deadline.
    assert (
        ADVISOR_REQUEST_TIMEOUT_S
        < DEFAULT_ADVISOR_TIMEOUT_S
    )

    # Post-flight artifact collection must
    # outlive the Advisor's outer deadline.
    assert (
        DEFAULT_ADVISOR_TIMEOUT_S
        < POST_FLIGHT_ADVISOR_GRACE_S
    )
