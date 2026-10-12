from communication.degradation_detector import (
    RadioDegradationDetector,
)

from communication.radio_map import (
    RadioMap,
    build_demo_radio_map,
)

from planner.coordinate_converter import (
    gps_to_local,
)


class CommunicationMonitor:
    """
    Runtime UAV communication-quality monitor.

    Responsibilities:
    1. Convert GPS position to local East/North coordinates.
    2. Query the Radio Map.
    3. Feed RSRP/SINR/coverage score into the
       degradation detector.
    4. Record communication samples.
    5. Record state-change events.
    """

    def __init__(
        self,
        origin_lat_deg: float,
        origin_lon_deg: float,
        radio_map: RadioMap | None = None,
        detector: RadioDegradationDetector | None = None,
    ):
        self.origin_lat_deg = (
            origin_lat_deg
        )

        self.origin_lon_deg = (
            origin_lon_deg
        )

        self.radio_map = (
            radio_map
            or build_demo_radio_map()
        )

        self.detector = (
            detector
            or RadioDegradationDetector()
        )

        self.samples: list[dict] = []
        self.events: list[dict] = []


    @property
    def state(self) -> str:
        return self.detector.state


    @property
    def latest_sample(
        self,
    ) -> dict | None:

        if not self.samples:
            return None

        return self.samples[-1]


    def process_local_position(
        self,
        east_m: float,
        north_m: float,
        altitude_m: float,
    ) -> dict:
        """
        Process one local-coordinate UAV position.
        """

        # Relative altitude close to zero may contain
        # tiny negative sensor/simulation errors.
        query_altitude_m = max(
            0.0,
            altitude_m,
        )

        radio = self.radio_map.query(
            east_m=east_m,
            north_m=north_m,
            altitude_m=query_altitude_m,
        )

        event = self.detector.update(
            rsrp_dbm=radio["rsrp_dbm"],
            sinr_db=radio["sinr_db"],
            coverage_score=(
                radio["coverage_score"]
            ),
        )

        sample = {
            "sample_index":
                len(self.samples),

            "east_m":
                east_m,

            "north_m":
                north_m,

            "altitude_m":
                query_altitude_m,

            "serving_bs":
                radio["serving_bs"],

            "distance_m":
                radio["distance_m"],

            "path_loss_db":
                radio["path_loss_db"],

            "rsrp_dbm":
                radio["rsrp_dbm"],

            "sinr_db":
                radio["sinr_db"],

            "coverage_score":
                radio["coverage_score"],

            "coverage_level":
                radio["coverage_level"],

            "monitor_state":
                self.detector.state,

            "event_type":
                (
                    event["event_type"]
                    if event
                    else None
                ),
        }

        self.samples.append(
            sample
        )

        if event is not None:

            enriched_event = {
                **event,

                "sample_index":
                    sample["sample_index"],

                "east_m":
                    east_m,

                "north_m":
                    north_m,

                "altitude_m":
                    query_altitude_m,

                "serving_bs":
                    radio["serving_bs"],
            }

            self.events.append(
                enriched_event
            )

        return sample


    def process_gps_position(
        self,
        latitude_deg: float,
        longitude_deg: float,
        relative_altitude_m: float,
    ) -> dict:
        """
        Convert GPS to local coordinates and
        process one communication sample.
        """

        east_m, north_m = (
            gps_to_local(
                origin_lat_deg=(
                    self.origin_lat_deg
                ),
                origin_lon_deg=(
                    self.origin_lon_deg
                ),
                latitude_deg=latitude_deg,
                longitude_deg=longitude_deg,
            )
        )

        return self.process_local_position(
            east_m=east_m,
            north_m=north_m,
            altitude_m=(
                relative_altitude_m
            ),
        )
