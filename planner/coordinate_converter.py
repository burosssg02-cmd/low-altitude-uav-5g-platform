import math

from planner.grid_map import GridNode


EARTH_RADIUS_M = 6378137.0


def grid_to_local(
    node: GridNode,
    origin_node: GridNode,
    resolution_m: float,
) -> tuple[float, float]:
    """
    Convert a grid node into local ENU coordinates.

    Returns:
        east_m, north_m

    Coordinate convention:
        grid x increases east
        grid y increases south

    Therefore:
        east  = +(x - origin_x)
        north = -(y - origin_y)
    """

    dx = node[0] - origin_node[0]
    dy = node[1] - origin_node[1]

    east_m = dx * resolution_m
    north_m = -dy * resolution_m

    return east_m, north_m


def local_to_gps(
    origin_lat_deg: float,
    origin_lon_deg: float,
    east_m: float,
    north_m: float,
) -> tuple[float, float]:
    """
    Convert local ENU displacement into approximate GPS coordinates.

    Suitable for short-distance UAV simulation.
    """

    origin_lat_rad = math.radians(
        origin_lat_deg
    )

    delta_lat_rad = (
        north_m / EARTH_RADIUS_M
    )

    delta_lon_rad = (
        east_m
        / (
            EARTH_RADIUS_M
            * math.cos(origin_lat_rad)
        )
    )

    target_lat_deg = (
        origin_lat_deg
        + math.degrees(delta_lat_rad)
    )

    target_lon_deg = (
        origin_lon_deg
        + math.degrees(delta_lon_rad)
    )

    return (
        target_lat_deg,
        target_lon_deg,
    )


def gps_to_local(
    origin_lat_deg: float,
    origin_lon_deg: float,
    latitude_deg: float,
    longitude_deg: float,
) -> tuple[float, float]:
    """
    Convert GPS coordinates into local ENU coordinates.

    Returns:
        east_m, north_m

    The origin GPS position is treated as:
        east = 0 m
        north = 0 m

    Suitable for short-distance UAV simulation.
    """

    origin_lat_rad = math.radians(
        origin_lat_deg
    )

    delta_lat_rad = math.radians(
        latitude_deg - origin_lat_deg
    )

    delta_lon_rad = math.radians(
        longitude_deg - origin_lon_deg
    )

    north_m = (
        delta_lat_rad
        * EARTH_RADIUS_M
    )

    east_m = (
        delta_lon_rad
        * EARTH_RADIUS_M
        * math.cos(origin_lat_rad)
    )

    return (
        east_m,
        north_m,
    )


def grid_to_gps(
    node: GridNode,
    origin_node: GridNode,
    origin_lat_deg: float,
    origin_lon_deg: float,
    resolution_m: float,
) -> tuple[float, float]:
    """
    Convert grid coordinates directly into GPS coordinates.
    """

    east_m, north_m = grid_to_local(
        node,
        origin_node,
        resolution_m,
    )

    return local_to_gps(
        origin_lat_deg,
        origin_lon_deg,
        east_m,
        north_m,
    )


def local_to_grid(
    east_m: float,
    north_m: float,
    origin_node: GridNode,
    resolution_m: float,
) -> GridNode:
    """
    Convert local ENU coordinates to the nearest grid node.

    Coordinate convention:
        grid x increases east
        grid y increases south

    Therefore:
        x = origin_x + east / resolution
        y = origin_y - north / resolution
    """

    if resolution_m <= 0:
        raise ValueError(
            "resolution_m must be positive"
        )

    grid_x = (
        origin_node[0]
        + int(
            round(
                east_m
                / resolution_m
            )
        )
    )

    grid_y = (
        origin_node[1]
        - int(
            round(
                north_m
                / resolution_m
            )
        )
    )

    return (
        grid_x,
        grid_y,
    )
