import unittest

from planner.waypoint_builder import build_gps_waypoints


class TestWaypointBuilder(unittest.TestCase):

    def test_build_gps_waypoints(self):

        simplified_path = [
            (1, 3),
            (3, 3),
            (3, 0),
            (8, 0),
            (8, 3),
        ]

        home_lat = 47.3979712
        home_lon = 8.5461636

        waypoints = build_gps_waypoints(
            path=simplified_path,
            origin_node=(1, 3),
            origin_lat_deg=home_lat,
            origin_lon_deg=home_lon,
            resolution_m=5.0,
            relative_altitude_m=5.0,
        )

        print("\nGPS waypoints:")

        for waypoint in waypoints:
            print(
                f"WP{waypoint.index}: "
                f"grid=({waypoint.grid_x}, "
                f"{waypoint.grid_y}) | "
                f"E={waypoint.east_m:.1f} m, "
                f"N={waypoint.north_m:.1f} m | "
                f"lat={waypoint.latitude_deg:.7f}, "
                f"lon={waypoint.longitude_deg:.7f} | "
                f"alt={waypoint.relative_altitude_m:.1f} m"
            )

        self.assertEqual(
            len(waypoints),
            5,
        )

        # WP0 should be exactly at home
        self.assertAlmostEqual(
            waypoints[0].latitude_deg,
            home_lat,
            places=6,
        )

        self.assertAlmostEqual(
            waypoints[0].longitude_deg,
            home_lon,
            places=6,
        )

        # WP1 = 10 m east
        self.assertAlmostEqual(
            waypoints[1].east_m,
            10.0,
        )

        self.assertAlmostEqual(
            waypoints[1].north_m,
            0.0,
        )

        # WP2 = 10 m east + 15 m north
        self.assertAlmostEqual(
            waypoints[2].east_m,
            10.0,
        )

        self.assertAlmostEqual(
            waypoints[2].north_m,
            15.0,
        )

        # Final goal = 35 m east
        self.assertAlmostEqual(
            waypoints[-1].east_m,
            35.0,
        )

        self.assertAlmostEqual(
            waypoints[-1].north_m,
            0.0,
        )


if __name__ == "__main__":
    unittest.main()
