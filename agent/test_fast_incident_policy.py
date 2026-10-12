from agent.fast_incident_policy import (
    decide_fast_incident_policy,
)


def make_comparison():
    return {
        "normal": {
            "planner":
                "normal",

            "planned_distance_m":
                30.0,

            "mean_coverage_score":
                0.5154795728,

            "min_coverage_score":
                0.4542049472,

            "mean_rsrp_dbm":
                -95.4383804,

            "min_rsrp_dbm":
                -98.6007479,

            "mean_sinr_db":
                1.0850687,

            "min_sinr_db":
                -0.0087876,

            "handover_count":
                2,
        },

        "communication_aware": {
            "planner":
                "communication_aware",

            "planned_distance_m":
                30.0,

            "mean_coverage_score":
                0.6753614865,

            "min_coverage_score":
                0.5018266066,

            "mean_rsrp_dbm":
                -86.2908105,

            "min_rsrp_dbm":
                -97.6520362,

            "mean_sinr_db":
                3.7588068,

            "min_sinr_db":
                1.6302427,

            "handover_count":
                0,
        },
    }


def test_real_incident_metrics_trigger_replan():
    result = (
        decide_fast_incident_policy(
            current_planner="normal",

            comparison=(
                make_comparison()
            ),
        )
    )

    assert (
        result["decision"]
        == "REPLAN_RECOMMENDED"
    )

    assert (
        result["selected_planner"]
        == "communication_aware"
    )

    assert (
        result["metrics"]
        ["mean_rsrp_gain_db"]
        > 9.0
    )

    assert (
        result["metrics"]
        ["communication_evidence_count"]
        >= 2
    )


def test_large_detour_keeps_route():
    comparison = make_comparison()

    comparison[
        "communication_aware"
    ][
        "planned_distance_m"
    ] = 50.0

    result = (
        decide_fast_incident_policy(
            current_planner="normal",
            comparison=comparison,
        )
    )

    assert (
        result["decision"]
        == "KEEP_ROUTE"
    )


def test_weak_improvement_keeps_route():
    comparison = make_comparison()

    comparison[
        "communication_aware"
    ].update(
        {
            "mean_coverage_score":
                0.54,

            "mean_rsrp_dbm":
                -93.5,

            "mean_sinr_db":
                1.5,

            "handover_count":
                2,
        }
    )

    result = (
        decide_fast_incident_policy(
            current_planner="normal",
            comparison=comparison,
        )
    )

    assert (
        result["decision"]
        == "KEEP_ROUTE"
    )


def test_already_communication_aware_keeps_route():
    result = (
        decide_fast_incident_policy(
            current_planner=(
                "communication_aware"
            ),

            comparison=(
                make_comparison()
            ),
        )
    )

    assert (
        result["decision"]
        == "KEEP_ROUTE"
    )

    assert (
        result["selected_planner"]
        == "communication_aware"
    )
