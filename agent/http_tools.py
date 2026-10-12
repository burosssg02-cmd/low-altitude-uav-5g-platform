import os

import httpx


DEFAULT_API_BASE_URL = (
    "http://127.0.0.1:8000"
)


def get_api_base_url() -> str:
    return os.getenv(
        "PLATFORM_API_BASE_URL",
        DEFAULT_API_BASE_URL,
    ).rstrip("/")


def request_json(
    method: str,
    path: str,
    json_body: dict | None = None,
) -> dict:
    """
    Call the UAV platform FastAPI backend.
    """

    url = (
        get_api_base_url()
        + path
    )

    try:
        response = httpx.request(
            method=method,
            url=url,
            json=json_body,
            timeout=15.0,
        )

    except httpx.RequestError as exc:
        raise RuntimeError(
            f"Backend request failed: {exc}"
        ) from exc

    if not response.is_success:
        raise RuntimeError(
            f"Backend returned "
            f"{response.status_code}: "
            f"{response.text}"
        )

    return response.json()


def backend_health_tool() -> dict:
    return request_json(
        method="GET",
        path="/health",
    )


def radio_query_api_tool(
    east_m: float,
    north_m: float,
    altitude_m: float = 5.0,
) -> dict:

    return request_json(
        method="POST",
        path="/radio/query",
        json_body={
            "east_m": east_m,
            "north_m": north_m,
            "altitude_m": altitude_m,
        },
    )


def mission_plan_api_tool(
    start: list[int],
    goal: list[int],
    altitude_m: float = 5.0,
    priority: str = "distance",
    communication_weight: float = 2.0,
) -> dict:
    """
    Create a PLANNED mission through FastAPI.
    """

    if priority == "communication":
        planner = "communication_aware"

    elif priority == "distance":
        planner = "normal"

    else:
        raise ValueError(
            "priority must be "
            "'distance' or 'communication'"
        )

    return request_json(
        method="POST",
        path="/missions/plan",
        json_body={
            "start": start,
            "goal": goal,
            "altitude_m": altitude_m,
            "planner": planner,
            "communication_weight":
                communication_weight,
        },
    )


def mission_status_api_tool(
    mission_id: str,
) -> dict:

    return request_json(
        method="GET",
        path=f"/missions/{mission_id}",
    )


# ============================================================
# Route Comparison Tool
# ============================================================

def route_compare_api_tool(
    start: list[int],
    goal: list[int],
    altitude_m: float = 5.0,
    communication_weight: float = 2.0,
    radio_origin: list[int] | None = None,
) -> dict:
    """
    Compare normal A* and communication-aware A*
    without creating a mission.
    """

    json_body = {
        "start": start,
        "goal": goal,
        "altitude_m": altitude_m,
        "communication_weight":
            communication_weight,
    }

    if radio_origin is not None:
        json_body["radio_origin"] = (
            radio_origin
        )

    return request_json(
        method="POST",
        path="/missions/compare",
        json_body=json_body,
    )
