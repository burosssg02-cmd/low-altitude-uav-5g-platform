import unittest

from planner.coordinate_converter import (
    gps_to_local,
    grid_to_gps,
    grid_to_local,
    local_to_gps,
)


class TestCoordinateConverter(unittest.TestCase):

    def test_grid_to_local(self):
        origin = (1, 3)

        east_m, north_m = grid_to_local(
            node=(3, 3),
            origin_node=origin,
            resolution_m=5.0,
        )

        self.assertAlmostEqual(
            east_m,
            10.0,
        )

        self.assertAlmostEqual(
            north_m,
            0.0,
        )

    def test_grid_to_gps(self):
        origin_node = (1, 3)

        origin_lat = 47.3979712
        origin_lon = 8.5461636

        target_lat, target_lon = grid_to_gps(
            node=(3, 3),
            origin_node=origin_node,
            origin_lat_deg=origin_lat,
            origin_lon_deg=origin_lon,
            resolution_m=5.0,
        )

        print(
            "\nOrigin GPS:"
            f" {origin_lat:.7f},"
            f" {origin_lon:.7f}"
        )

        print(
            "Target GPS:"
            f" {target_lat:.7f},"
            f" {target_lon:.7f}"
        )

        self.assertAlmostEqual(
            target_lat,
            origin_lat,
            places=5,
        )

        self.assertGreater(
            target_lon,
            origin_lon,
        )

    def test_gps_to_local(self):
        origin_lat = 47.3979712
        origin_lon = 8.5461636

        target_lat, target_lon = local_to_gps(
            origin_lat_deg=origin_lat,
            origin_lon_deg=origin_lon,
            east_m=10.0,
            north_m=15.0,
        )

        east_m, north_m = gps_to_local(
            origin_lat_deg=origin_lat,
            origin_lon_deg=origin_lon,
            latitude_deg=target_lat,
            longitude_deg=target_lon,
        )

        print(
            "\nGPS -> Local:"
            f" E={east_m:.3f} m,"
            f" N={north_m:.3f} m"
        )

        self.assertAlmostEqual(
            east_m,
            10.0,
            places=3,
        )

        self.assertAlmostEqual(
            north_m,
            15.0,
            places=3,
        )

    def test_local_gps_round_trip(self):
        origin_lat = 47.3979712
        origin_lon = 8.5461636

        expected_east = 35.0
        expected_north = 15.0

        latitude, longitude = local_to_gps(
            origin_lat_deg=origin_lat,
            origin_lon_deg=origin_lon,
            east_m=expected_east,
            north_m=expected_north,
        )

        actual_east, actual_north = gps_to_local(
            origin_lat_deg=origin_lat,
            origin_lon_deg=origin_lon,
            latitude_deg=latitude,
            longitude_deg=longitude,
        )

        print(
            "\nRound trip:"
            f" expected=({expected_east:.1f},"
            f" {expected_north:.1f}) m,"
            f" actual=({actual_east:.3f},"
            f" {actual_north:.3f}) m"
        )

        self.assertAlmostEqual(
            actual_east,
            expected_east,
            places=3,
        )

        self.assertAlmostEqual(
            actual_north,
            expected_north,
            places=3,
        )


if __name__ == "__main__":
    unittest.main()


def test_local_to_grid_exact_node():
    from planner.coordinate_converter import (
        local_to_grid,
    )

    node = local_to_grid(
        east_m=20.0,
        north_m=15.0,
        origin_node=(1, 3),
        resolution_m=5.0,
    )

    assert node == (5, 0)


def test_local_to_grid_real_incident_position():
    from planner.coordinate_converter import (
        local_to_grid,
    )

    node = local_to_grid(
        east_m=22.4,
        north_m=14.9,
        origin_node=(1, 3),
        resolution_m=5.0,
    )

    assert node == (5, 0)


def test_grid_local_round_trip():
    from planner.coordinate_converter import (
        grid_to_local,
        local_to_grid,
    )

    origin = (1, 3)

    nodes = [
        (1, 3),
        (3, 3),
        (3, 0),
        (5, 0),
        (8, 3),
        (1, 7),
        (5, 7),
    ]

    for node in nodes:
        east_m, north_m = (
            grid_to_local(
                node=node,
                origin_node=origin,
                resolution_m=5.0,
            )
        )

        restored = local_to_grid(
            east_m=east_m,
            north_m=north_m,
            origin_node=origin,
            resolution_m=5.0,
        )

        assert restored == node
