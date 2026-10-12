from dataclasses import dataclass

from planner.coordinate_converter import (
    grid_to_gps,
    grid_to_local,
)
from planner.grid_map import GridNode


@dataclass
class GpsWaypoint:
    index: int

    grid_x: int
    grid_y: int

    east_m: float
    north_m: float

    latitude_deg: float
    longitude_deg: float

    relative_altitude_m: float


def build_gps_waypoints(
    path: list[GridNode],
    origin_node: GridNode,
    origin_lat_deg: float,
    origin_lon_deg: float,
    resolution_m: float,
    relative_altitude_m: float,
) -> list[GpsWaypoint]:
    """
    Convert simplified A* grid path into GPS waypoints.

    The first path node is normally the UAV home/start point.
    """

    waypoints: list[GpsWaypoint] = []

    for index, node in enumerate(path):

        east_m, north_m = grid_to_local(
            node=node,
            origin_node=origin_node,
            resolution_m=resolution_m,
        )

        latitude_deg, longitude_deg = grid_to_gps(
            node=node,
            origin_node=origin_node,
            origin_lat_deg=origin_lat_deg,
            origin_lon_deg=origin_lon_deg,
            resolution_m=resolution_m,
        )

        waypoint = GpsWaypoint(
            index=index,
            grid_x=node[0],
            grid_y=node[1],
            east_m=east_m,
            north_m=north_m,
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            relative_altitude_m=relative_altitude_m,
        )

        waypoints.append(waypoint)

    return waypoints
