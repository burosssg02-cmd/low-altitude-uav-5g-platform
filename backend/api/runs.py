import mimetypes

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from fastapi.responses import (
    FileResponse,
)

from backend.services import (
    run_artifact_service,
)


router = APIRouter(
    prefix="/runs",
    tags=["dashboard-runs"],
)


@router.get("")
async def get_runs():
    """
    List persisted mission/run artifacts
    for the Dashboard.
    """

    runs = (
        run_artifact_service
        .list_runs()
    )

    return {
        "count": len(runs),
        "runs": runs,
    }


@router.get("/{run_id}/trajectory")
async def get_run_trajectory(
    run_id: str,
    stride: int = Query(
        default=1,
        ge=1,
        le=100,
        description=(
            "Return every Nth trajectory "
            "sample."
        ),
    ),
):
    """
    Return trajectory and communication
    samples for one persisted run.
    """

    try:
        return (
            run_artifact_service
            .get_run_trajectory(
                run_id=run_id,
                stride=stride,
            )
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Run or trajectory artifact "
                f"not found: {run_id}"
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get("/{run_id}/incidents")
async def get_run_incidents(
    run_id: str,
):
    """
    Return normalized communication degradation,
    replan, recovery, and Advisor episodes.
    """

    try:
        return (
            run_artifact_service
            .get_run_incidents(
                run_id=run_id
            )
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Run or multi-replan artifact "
                f"not found: {run_id}"
            ),
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        )


@router.get(
    "/{run_id}/artifacts/{artifact_name}"
)
async def get_run_artifact(
    run_id: str,
    artifact_name: str,
    download: bool = Query(
        default=False,
        description=(
            "Force the artifact to be downloaded "
            "instead of displayed inline."
        ),
    ),
):
    """
    Return one persisted artifact file.

    Images, JSON, CSV, and other files can be
    consumed directly by the Dashboard.
    """

    try:
        artifact_path = (
            run_artifact_service
            .get_run_artifact_path(
                run_id=run_id,
                artifact_name=artifact_name,
            )
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                "Artifact not found: "
                f"{artifact_name}"
            ),
        )

    media_type, _ = (
        mimetypes.guess_type(
            str(artifact_path)
        )
    )

    if media_type is None:
        media_type = (
            "application/octet-stream"
        )

    if download:
        return FileResponse(
            path=artifact_path,
            media_type=media_type,
            filename=artifact_path.name,
        )

    return FileResponse(
        path=artifact_path,
        media_type=media_type,
    )


@router.get("/{run_id}")
async def get_run(
    run_id: str,
):
    """
    Return one persisted run summary
    and its artifact manifest.

    Large payloads are exposed
    by dedicated endpoints.
    """

    try:
        return (
            run_artifact_service
            .get_run_detail(
                run_id
            )
        )

    except FileNotFoundError:
        raise HTTPException(
            status_code=404,
            detail=(
                f"Run not found: "
                f"{run_id}"
            ),
        )
