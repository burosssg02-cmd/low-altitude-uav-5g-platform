import math
from dataclasses import dataclass


# ============================================================
# Data models
# ============================================================

@dataclass
class BaseStation:
    bs_id: str

    east_m: float
    north_m: float
    altitude_m: float

    frequency_ghz: float = 3.5

    # Reference-signal power used by the simplified
    # Radio Map model, not total BS transmit power.
    reference_signal_power_dbm: float = 0.0

    path_loss_exponent: float = 2.2


@dataclass
class WeakCoverageZone:
    """
    Simplified attenuation region.

    This is used only for the V0.4 baseline so that
    communication-aware planning has meaningful
    coverage differences.

    Later it can be replaced by:
    - ray tracing
    - measured Radio Map
    - learned propagation model
    """

    min_east_m: float
    max_east_m: float

    min_north_m: float
    max_north_m: float

    min_altitude_m: float
    max_altitude_m: float

    extra_loss_db: float


# ============================================================
# Radio Map
# ============================================================

class RadioMap:
    def __init__(
        self,
        base_stations,
        weak_zones=None,
        noise_bandwidth_hz: float = 180_000.0,
        noise_figure_db: float = 7.0,
    ):
        if not base_stations:
            raise ValueError(
                "At least one base station is required"
            )

        self.base_stations = list(
            base_stations
        )

        self.weak_zones = list(
            weak_zones or []
        )

        self.noise_bandwidth_hz = (
            noise_bandwidth_hz
        )

        self.noise_figure_db = (
            noise_figure_db
        )


    # --------------------------------------------------------
    # Basic RF utilities
    # --------------------------------------------------------

    @staticmethod
    def _dbm_to_mw(
        power_dbm: float,
    ) -> float:
        return 10 ** (
            power_dbm / 10.0
        )


    @staticmethod
    def _mw_to_dbm(
        power_mw: float,
    ) -> float:
        return 10.0 * math.log10(
            power_mw
        )


    @staticmethod
    def _clip(
        value: float,
        minimum: float,
        maximum: float,
    ) -> float:
        return max(
            minimum,
            min(
                value,
                maximum,
            ),
        )


    # --------------------------------------------------------
    # Geometry
    # --------------------------------------------------------

    @staticmethod
    def _distance_3d_m(
        east_m: float,
        north_m: float,
        altitude_m: float,
        bs: BaseStation,
    ) -> float:

        delta_east = (
            east_m
            - bs.east_m
        )

        delta_north = (
            north_m
            - bs.north_m
        )

        delta_altitude = (
            altitude_m
            - bs.altitude_m
        )

        return math.sqrt(
            delta_east ** 2
            + delta_north ** 2
            + delta_altitude ** 2
        )


    # --------------------------------------------------------
    # Propagation model
    # --------------------------------------------------------

    @staticmethod
    def _fspl_1m_db(
        frequency_ghz: float,
    ) -> float:
        """
        Free-space path loss at 1 meter.

        FSPL(1m) =
        32.4 + 20*log10(fc_GHz)
        """

        return (
            32.4
            + 20.0
            * math.log10(
                frequency_ghz
            )
        )


    def _extra_loss_db(
        self,
        east_m: float,
        north_m: float,
        altitude_m: float,
    ) -> float:

        total_loss = 0.0

        for zone in self.weak_zones:

            inside = (
                zone.min_east_m
                <= east_m
                <= zone.max_east_m

                and

                zone.min_north_m
                <= north_m
                <= zone.max_north_m

                and

                zone.min_altitude_m
                <= altitude_m
                <= zone.max_altitude_m
            )

            if inside:
                total_loss += (
                    zone.extra_loss_db
                )

        return total_loss


    def _path_loss_db(
        self,
        east_m: float,
        north_m: float,
        altitude_m: float,
        bs: BaseStation,
    ) -> float:

        distance_m = self._distance_3d_m(
            east_m,
            north_m,
            altitude_m,
            bs,
        )

        # CI model uses 1 m reference distance.
        distance_m = max(
            distance_m,
            1.0,
        )

        fspl_1m = self._fspl_1m_db(
            bs.frequency_ghz
        )

        path_loss = (
            fspl_1m
            + 10.0
            * bs.path_loss_exponent
            * math.log10(
                distance_m
            )
        )

        path_loss += self._extra_loss_db(
            east_m,
            north_m,
            altitude_m,
        )

        return path_loss


    # --------------------------------------------------------
    # Coverage quality
    # --------------------------------------------------------

    @staticmethod
    def _coverage_level(
        rsrp_dbm: float,
        sinr_db: float,
    ) -> str:

        if (
            rsrp_dbm >= -90.0
            and sinr_db >= 10.0
        ):
            return "GOOD"

        if (
            rsrp_dbm >= -105.0
            and sinr_db >= 0.0
        ):
            return "FAIR"

        return "POOR"


    def _coverage_score(
        self,
        rsrp_dbm: float,
        sinr_db: float,
    ) -> float:
        """
        Normalize communication quality to [0, 1].

        RSRP:
            -120 dBm -> 0
             -80 dBm -> 1

        SINR:
            -10 dB -> 0
             20 dB -> 1
        """

        rsrp_score = self._clip(
            (
                rsrp_dbm
                + 120.0
            )
            / 40.0,
            0.0,
            1.0,
        )

        sinr_score = self._clip(
            (
                sinr_db
                + 10.0
            )
            / 30.0,
            0.0,
            1.0,
        )

        score = (
            0.6 * rsrp_score
            + 0.4 * sinr_score
        )

        return self._clip(
            score,
            0.0,
            1.0,
        )


    # --------------------------------------------------------
    # Public query API
    # --------------------------------------------------------

    def query(
        self,
        east_m: float,
        north_m: float,
        altitude_m: float,
    ) -> dict:
        """
        Query communication quality at a 3D point.
        """

        bs_results = []

        for bs in self.base_stations:

            distance_m = (
                self._distance_3d_m(
                    east_m,
                    north_m,
                    altitude_m,
                    bs,
                )
            )

            path_loss_db = (
                self._path_loss_db(
                    east_m,
                    north_m,
                    altitude_m,
                    bs,
                )
            )

            rsrp_dbm = (
                bs.reference_signal_power_dbm
                - path_loss_db
            )

            bs_results.append(
                {
                    "bs_id":
                        bs.bs_id,

                    "distance_m":
                        distance_m,

                    "path_loss_db":
                        path_loss_db,

                    "rsrp_dbm":
                        rsrp_dbm,
                }
            )

        # strongest RSRP becomes serving BS
        serving = max(
            bs_results,
            key=lambda item:
                item["rsrp_dbm"],
        )

        signal_mw = (
            self._dbm_to_mw(
                serving["rsrp_dbm"]
            )
        )

        interference_mw = sum(
            self._dbm_to_mw(
                item["rsrp_dbm"]
            )
            for item in bs_results
            if item["bs_id"]
            != serving["bs_id"]
        )

        noise_dbm = (
            -174.0
            + 10.0
            * math.log10(
                self.noise_bandwidth_hz
            )
            + self.noise_figure_db
        )

        noise_mw = (
            self._dbm_to_mw(
                noise_dbm
            )
        )

        sinr_linear = (
            signal_mw
            / (
                interference_mw
                + noise_mw
            )
        )

        sinr_db = (
            10.0
            * math.log10(
                sinr_linear
            )
        )

        coverage_score = (
            self._coverage_score(
                serving["rsrp_dbm"],
                sinr_db,
            )
        )

        coverage_level = (
            self._coverage_level(
                serving["rsrp_dbm"],
                sinr_db,
            )
        )

        return {
            "east_m":
                east_m,

            "north_m":
                north_m,

            "altitude_m":
                altitude_m,

            "serving_bs":
                serving["bs_id"],

            "distance_m":
                serving["distance_m"],

            "path_loss_db":
                serving["path_loss_db"],

            "rsrp_dbm":
                serving["rsrp_dbm"],

            "sinr_db":
                sinr_db,

            "coverage_score":
                coverage_score,

            "coverage_level":
                coverage_level,
        }


# ============================================================
# Demo Radio Map
# ============================================================

def build_demo_radio_map() -> RadioMap:
    """
    Build the first synthetic 5G Radio Map.

    The layout is deliberately designed to contain
    a weak-coverage area so that V0.5 can demonstrate
    communication-aware path planning.
    """

    base_stations = [
        BaseStation(
            bs_id="BS1",
            east_m=0.0,
            north_m=-20.0,
            altitude_m=25.0,
            frequency_ghz=3.5,
            reference_signal_power_dbm=0.0,
            path_loss_exponent=2.2,
        ),

        BaseStation(
            bs_id="BS2",
            east_m=60.0,
            north_m=25.0,
            altitude_m=30.0,
            frequency_ghz=3.5,
            reference_signal_power_dbm=-2.0,
            path_loss_exponent=2.2,
        ),
    ]

    weak_zones = [
        WeakCoverageZone(
            min_east_m=20.0,
            max_east_m=35.0,
            min_north_m=5.0,
            max_north_m=20.0,
            min_altitude_m=0.0,
            max_altitude_m=20.0,
            extra_loss_db=18.0,
        ),
    ]

    return RadioMap(
        base_stations=base_stations,
        weak_zones=weak_zones,
    )
