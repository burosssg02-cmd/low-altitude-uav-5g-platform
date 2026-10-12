from datetime import datetime, timezone

from fastapi import FastAPI

from backend.api.runs import router as runs_router
from backend.api.dashboard import router as dashboard_router

from backend.api.agent import (
    router as agent_router,
)

from backend.api.missions import (
    router as missions_router,
)

from backend.api.radio import (
    router as radio_router,
)


app = FastAPI(
    title="Low-Altitude UAV Agent Platform API",
    description=(
        "Backend API for UAV mission planning, "
        "execution, 5G communication assurance, "
        "and Agent orchestration."
    ),
    version="0.6.5",
)


app.include_router(
    agent_router
)

app.include_router(
    missions_router
)

app.include_router(
    radio_router
)

app.include_router(
    runs_router
)

app.include_router(
    dashboard_router
)


@app.get("/")
async def root():
    return {
        "service": "low-altitude-uav-agent-platform",
        "status": "running",
        "version": "0.6.5",
    }


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "backend",
        "version": "0.6.5",
        "timestamp_utc": datetime.now(
            timezone.utc
        ).isoformat(),
    }
