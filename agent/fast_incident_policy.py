from __future__ import annotations


# ============================================================
# Runtime policy thresholds
# ============================================================

# Communication-aware route may be longer, but an excessive
# detour is not accepted by the real-time policy.
MAX_DISTANCE_RATIO = 1.35

# Required communication improvements.
MIN_MEAN_SCORE_GAIN = 0.08
MIN_MEAN_RSRP_GAIN_DB = 3.0
MIN_MEAN_SINR_GAIN_DB = 1.0


def _metric(
    route: dict,
    name: str,
) -> float:
    value = route.get(name)

    if value is None:
        raise ValueError(
            f"Missing route metric: {name}"
        )

    return float(value)


def decide_fast_incident_policy(
    *,
    current_planner: str,
    comparison: dict,
) -> dict:
    """
    Deterministic real-time decision policy.

    This function contains no LLM call.

    Flight-critical decisions are made only from
    deterministic route-comparison metrics.
    """

    if current_planner not in {
        "normal",
        "communication_aware",
    }:
        raise ValueError(
            "Unsupported current planner: "
            f"{current_planner}"
        )

    normal = comparison.get(
        "normal"
    )

    communication = comparison.get(
        "communication_aware"
    )

    if not isinstance(normal, dict):
        raise ValueError(
            "Missing normal route result"
        )

    if not isinstance(
        communication,
        dict,
    ):
        raise ValueError(
            "Missing communication-aware "
            "route result"
        )

    # --------------------------------------------------------
    # Already using communication-aware routing.
    # Avoid unnecessary repeated replanning.
    # --------------------------------------------------------

    if (
        current_planner
        == "communication_aware"
    ):
        return {
            "decision":
                "KEEP_ROUTE",

            "selected_planner":
                "communication_aware",

            "reason": (
                "Current mission is already using "
                "communication-aware routing."
            ),

            "triggered_rules": [
                "ALREADY_COMMUNICATION_AWARE"
            ],

            "metrics": {},
        }

    # --------------------------------------------------------
    # Read deterministic metrics
    # --------------------------------------------------------

    normal_distance = _metric(
        normal,
        "planned_distance_m",
    )

    communication_distance = _metric(
        communication,
        "planned_distance_m",
    )

    normal_score = _metric(
        normal,
        "mean_coverage_score",
    )

    communication_score = _metric(
        communication,
        "mean_coverage_score",
    )

    normal_rsrp = _metric(
        normal,
        "mean_rsrp_dbm",
    )

    communication_rsrp = _metric(
        communication,
        "mean_rsrp_dbm",
    )

    normal_sinr = _metric(
        normal,
        "mean_sinr_db",
    )

    communication_sinr = _metric(
        communication,
        "mean_sinr_db",
    )

    normal_handovers = int(
        normal.get(
            "handover_count",
            0,
        )
    )

    communication_handovers = int(
        communication.get(
            "handover_count",
            0,
        )
    )

    if normal_distance <= 0:
        raise ValueError(
            "Normal route distance must be > 0"
        )

    distance_ratio = (
        communication_distance
        / normal_distance
    )

    score_gain = (
        communication_score
        - normal_score
    )

    rsrp_gain_db = (
        communication_rsrp
        - normal_rsrp
    )

    sinr_gain_db = (
        communication_sinr
        - normal_sinr
    )

    handover_gain = (
        normal_handovers
        - communication_handovers
    )

    # --------------------------------------------------------
    # Deterministic evidence
    # --------------------------------------------------------

    triggered_rules = []

    if (
        score_gain
        >= MIN_MEAN_SCORE_GAIN
    ):
        triggered_rules.append(
            "MEAN_SCORE_IMPROVED"
        )

    if (
        rsrp_gain_db
        >= MIN_MEAN_RSRP_GAIN_DB
    ):
        triggered_rules.append(
            "MEAN_RSRP_IMPROVED"
        )

    if (
        sinr_gain_db
        >= MIN_MEAN_SINR_GAIN_DB
    ):
        triggered_rules.append(
            "MEAN_SINR_IMPROVED"
        )

    if handover_gain > 0:
        triggered_rules.append(
            "FEWER_HANDOVERS"
        )

    distance_acceptable = (
        distance_ratio
        <= MAX_DISTANCE_RATIO
    )

    # At least two independent communication
    # improvements are required.
    communication_evidence_count = (
        int(
            score_gain
            >= MIN_MEAN_SCORE_GAIN
        )
        + int(
            rsrp_gain_db
            >= MIN_MEAN_RSRP_GAIN_DB
        )
        + int(
            sinr_gain_db
            >= MIN_MEAN_SINR_GAIN_DB
        )
        + int(
            handover_gain > 0
        )
    )

    should_replan = (
        distance_acceptable
        and communication_evidence_count
        >= 2
    )

    metrics = {
        "normal_distance_m":
            normal_distance,

        "communication_distance_m":
            communication_distance,

        "distance_ratio":
            distance_ratio,

        "mean_score_gain":
            score_gain,

        "mean_rsrp_gain_db":
            rsrp_gain_db,

        "mean_sinr_gain_db":
            sinr_gain_db,

        "handover_reduction":
            handover_gain,

        "communication_evidence_count":
            communication_evidence_count,
    }

    if should_replan:
        return {
            "decision":
                "REPLAN_RECOMMENDED",

            "selected_planner":
                "communication_aware",

            "reason": (
                "Deterministic runtime policy "
                "found sufficient communication "
                "improvement within the allowed "
                "distance penalty."
            ),

            "triggered_rules":
                triggered_rules,

            "metrics":
                metrics,
        }

    return {
        "decision":
            "KEEP_ROUTE",

        "selected_planner":
            current_planner,

        "reason": (
            "Communication improvement is "
            "insufficient or the route distance "
            "penalty exceeds the runtime limit."
        ),

        "triggered_rules":
            triggered_rules,

        "metrics":
            metrics,
    }
