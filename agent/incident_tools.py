from agent.http_tools import (
    route_compare_api_tool,
)
from agent.incident_context import (
    IncidentContext,
)


def compare_incident_routes(
    context: IncidentContext,
) -> dict:
    """
    Compare remaining route options for a
    runtime communication incident.

    Search starts from current UAV grid node,
    while Radio Map coordinates remain
    referenced to the original mission start.
    """

    return route_compare_api_tool(
        start=list(
            context.current_grid
        ),
        goal=list(
            context.mission_goal
        ),
        altitude_m=(
            context.altitude_m
        ),
        communication_weight=(
            context.communication_weight
        ),
        radio_origin=list(
            context.mission_start
        ),
    )
