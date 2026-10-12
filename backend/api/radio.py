from fastapi import APIRouter

from backend.schemas import (
    RadioQueryRequest,
    RadioQueryResponse,
)

from backend.services.radio_service import (
    query_radio_map,
)


router = APIRouter(
    prefix="/radio",
    tags=["radio"],
)


@router.post(
    "/query",
    response_model=RadioQueryResponse,
)
async def query_radio(
    request: RadioQueryRequest,
):
    return query_radio_map(
        request
    )
