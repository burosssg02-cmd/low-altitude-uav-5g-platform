from backend.schemas import (
    RadioQueryRequest,
    RadioQueryResponse,
)

from communication.radio_map import (
    build_demo_radio_map,
)


# V0.4 baseline Radio Map.
#
# Later this object can be replaced by:
# - measured Radio Map
# - ray tracing results
# - ML propagation model
# without changing the API layer.
RADIO_MAP = build_demo_radio_map()


def query_radio_map(
    request: RadioQueryRequest,
) -> RadioQueryResponse:

    result = RADIO_MAP.query(
        east_m=request.east_m,
        north_m=request.north_m,
        altitude_m=request.altitude_m,
    )

    return RadioQueryResponse(
        **result
    )
