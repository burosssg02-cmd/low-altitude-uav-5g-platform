import unittest

from communication.radio_map import (
    BaseStation,
    RadioMap,
    WeakCoverageZone,
    build_demo_radio_map,
)


class TestRadioMap(unittest.TestCase):

    def test_query_returns_valid_result(
        self,
    ):
        radio_map = (
            build_demo_radio_map()
        )

        result = radio_map.query(
            east_m=10.0,
            north_m=0.0,
            altitude_m=5.0,
        )

        self.assertIn(
            result["serving_bs"],
            {"BS1", "BS2"},
        )

        self.assertTrue(
            0.0
            <= result["coverage_score"]
            <= 1.0
        )

        self.assertIn(
            result["coverage_level"],
            {"GOOD", "FAIR", "POOR"},
        )


    def test_weak_zone_reduces_rsrp(
        self,
    ):
        bs = BaseStation(
            bs_id="BS_TEST",
            east_m=0.0,
            north_m=0.0,
            altitude_m=25.0,
            frequency_ghz=3.5,
            reference_signal_power_dbm=0.0,
            path_loss_exponent=2.0,
        )

        normal_map = RadioMap(
            base_stations=[bs]
        )

        weak_map = RadioMap(
            base_stations=[bs],
            weak_zones=[
                WeakCoverageZone(
                    min_east_m=20.0,
                    max_east_m=40.0,
                    min_north_m=0.0,
                    max_north_m=20.0,
                    min_altitude_m=0.0,
                    max_altitude_m=20.0,
                    extra_loss_db=20.0,
                )
            ],
        )

        normal = normal_map.query(
            east_m=30.0,
            north_m=10.0,
            altitude_m=5.0,
        )

        weak = weak_map.query(
            east_m=30.0,
            north_m=10.0,
            altitude_m=5.0,
        )

        difference = (
            normal["rsrp_dbm"]
            - weak["rsrp_dbm"]
        )

        self.assertAlmostEqual(
            difference,
            20.0,
            places=6,
        )


    def test_near_bs_is_stronger(
        self,
    ):
        radio_map = (
            build_demo_radio_map()
        )

        near = radio_map.query(
            east_m=0.0,
            north_m=-15.0,
            altitude_m=5.0,
        )

        far = radio_map.query(
            east_m=25.0,
            north_m=10.0,
            altitude_m=5.0,
        )

        self.assertGreater(
            near["rsrp_dbm"],
            far["rsrp_dbm"],
        )


if __name__ == "__main__":
    unittest.main()
