from dataclasses import (
    dataclass,
)


@dataclass
class DegradationConfig:
    """
    Runtime communication degradation thresholds.
    """

    degraded_rsrp_dbm: float = -95.0
    degraded_sinr_db: float = 0.0
    degraded_score: float = 0.55

    recovery_rsrp_dbm: float = -92.0
    recovery_sinr_db: float = 1.0
    recovery_score: float = 0.65

    trigger_samples: int = 3
    recovery_samples: int = 3


class RadioDegradationDetector:
    """
    Stateful radio degradation detector with
    consecutive-sample filtering and hysteresis.
    """

    def __init__(
        self,
        config: DegradationConfig | None = None,
    ):
        self.config = (
            config
            or DegradationConfig()
        )

        self.state = "NORMAL"

        self.bad_count = 0
        self.good_count = 0


    def _degradation_reasons(
        self,
        rsrp_dbm: float,
        sinr_db: float,
        coverage_score: float,
    ) -> list[str]:

        reasons = []

        if (
            rsrp_dbm
            <= self.config.degraded_rsrp_dbm
        ):
            reasons.append("LOW_RSRP")

        if (
            sinr_db
            <= self.config.degraded_sinr_db
        ):
            reasons.append("LOW_SINR")

        if (
            coverage_score
            <= self.config.degraded_score
        ):
            reasons.append(
                "LOW_COVERAGE_SCORE"
            )

        return reasons


    def _is_recovered(
        self,
        rsrp_dbm: float,
        sinr_db: float,
        coverage_score: float,
    ) -> bool:

        return (
            rsrp_dbm
            >= self.config.recovery_rsrp_dbm

            and sinr_db
            >= self.config.recovery_sinr_db

            and coverage_score
            >= self.config.recovery_score
        )


    def update(
        self,
        rsrp_dbm: float,
        sinr_db: float,
        coverage_score: float,
    ) -> dict | None:
        """
        Feed one radio sample.

        Returns an event dictionary only when the
        communication state changes.
        """

        reasons = (
            self._degradation_reasons(
                rsrp_dbm=rsrp_dbm,
                sinr_db=sinr_db,
                coverage_score=(
                    coverage_score
                ),
            )
        )

        # ====================================================
        # NORMAL -> DEGRADED
        # ====================================================

        if self.state == "NORMAL":

            if reasons:
                self.bad_count += 1
            else:
                self.bad_count = 0

            self.good_count = 0

            if (
                self.bad_count
                >= self.config.trigger_samples
            ):
                self.state = "DEGRADED"
                self.bad_count = 0

                return {
                    "event_type":
                        "COMMUNICATION_DEGRADED",

                    "state":
                        self.state,

                    "rsrp_dbm":
                        rsrp_dbm,

                    "sinr_db":
                        sinr_db,

                    "coverage_score":
                        coverage_score,

                    "reasons":
                        reasons,
                }

            return None

        # ====================================================
        # DEGRADED -> NORMAL
        # ====================================================

        if self._is_recovered(
            rsrp_dbm=rsrp_dbm,
            sinr_db=sinr_db,
            coverage_score=coverage_score,
        ):
            self.good_count += 1
        else:
            self.good_count = 0

        self.bad_count = 0

        if (
            self.good_count
            >= self.config.recovery_samples
        ):
            self.state = "NORMAL"
            self.good_count = 0

            return {
                "event_type":
                    "COMMUNICATION_RECOVERED",

                "state":
                    self.state,

                "rsrp_dbm":
                    rsrp_dbm,

                "sinr_db":
                    sinr_db,

                "coverage_score":
                    coverage_score,

                "reasons": [],
            }

        return None
