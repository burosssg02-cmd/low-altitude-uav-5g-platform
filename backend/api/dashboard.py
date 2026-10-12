from fastapi import APIRouter

from backend.services import run_artifact_service


router = APIRouter(
    prefix="/dashboard",
    tags=["dashboard"],
)


@router.get("/overview")
async def get_dashboard_overview():
    """
    Return summary data for the Dashboard overview page.

    The latest persisted run may be PARTIAL, so the response
    separately exposes the latest run and the latest COMPLETE run.
    """

    runs = run_artifact_service.list_runs()

    complete_runs = [
        run
        for run in runs
        if run.get("artifact_status") == "COMPLETE"
    ]

    partial_runs = [
        run
        for run in runs
        if run.get("artifact_status") == "PARTIAL"
    ]

    latest_run = runs[0] if runs else None

    latest_complete_run = (
        complete_runs[0]
        if complete_runs
        else None
    )

    return {
        "runs_total": len(runs),
        "complete_runs": len(complete_runs),
        "partial_runs": len(partial_runs),
        "latest_run": latest_run,
        "latest_complete_run": latest_complete_run,
    }
