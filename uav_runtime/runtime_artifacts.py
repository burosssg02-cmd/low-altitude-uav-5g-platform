from __future__ import annotations

import json

from dataclasses import (
    asdict,
    is_dataclass,
)

from datetime import (
    datetime,
    timezone,
)

from pathlib import Path
from typing import Any


def _utc_now() -> str:
    return (
        datetime.now(
            timezone.utc
        )
        .isoformat()
    )


def _json_safe(
    value: Any,
) -> Any:
    """
    Convert runtime objects into JSON-safe
    structures without losing ordinary numeric
    and dictionary data.
    """

    if value is None:
        return None

    if isinstance(
        value,
        (
            str,
            int,
            float,
            bool,
        ),
    ):
        return value

    if isinstance(
        value,
        Path,
    ):
        return str(
            value
        )

    if is_dataclass(
        value
    ):
        return _json_safe(
            asdict(
                value
            )
        )

    if isinstance(
        value,
        dict,
    ):
        return {
            str(key):
                _json_safe(
                    item
                )
            for key, item
            in value.items()
        }

    if isinstance(
        value,
        (
            list,
            tuple,
            set,
        ),
    ):
        return [
            _json_safe(
                item
            )
            for item in value
        ]

    if hasattr(
        value,
        "to_dict",
    ):
        try:
            return _json_safe(
                value.to_dict()
            )
        except Exception:
            pass

    return str(
        value
    )


def save_runtime_artifacts(
    *,
    run_dir: Path,
    mission_id: str,
    mission_metadata: dict | None = None,
    incident_handler=None,
    communication_monitor=None,
    route_events: list[dict] | None = None,
) -> dict:
    """
    Persist runtime incident / replan artifacts.

    This function is post-flight bookkeeping only.
    It has no authority over PX4 or route decisions.
    """

    run_dir = Path(
        run_dir
    )

    run_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    incident_records = []

    if incident_handler is not None:
        incident_records = list(
            getattr(
                incident_handler,
                "records",
                [],
            )
        )

    communication_events = []

    if communication_monitor is not None:
        communication_events = list(
            getattr(
                communication_monitor,
                "events",
                [],
            )
        )

    route_events = list(
        route_events
        or []
    )

    incident_document = {
        "schema_version":
            "1.0",

        "generated_at_utc":
            _utc_now(),

        "mission_id":
            mission_id,

        "mission":
            mission_metadata
            or {},

        "incident_records":
            incident_records,

        "communication_events":
            communication_events,
    }

    incident_document = (
        _json_safe(
            incident_document
        )
    )

    incident_path = (
        run_dir
        / "incident_events.json"
    )

    incident_path.write_text(
        json.dumps(
            incident_document,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    replan_records = [
        item
        for item
        in incident_records
        if (
            isinstance(
                item,
                dict,
            )
            and item.get(
                "action"
            )
            == "REPLAN_QUEUED"
        )
    ]

    replan_document = {
        "schema_version":
            "1.0",

        "generated_at_utc":
            _utc_now(),

        "mission_id":
            mission_id,

        "replan_decisions":
            replan_records,

        "route_application_events":
            route_events,
    }

    replan_document = (
        _json_safe(
            replan_document
        )
    )

    replan_path = (
        run_dir
        / "runtime_replans.json"
    )

    replan_path.write_text(
        json.dumps(
            replan_document,
            indent=2,
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )

    print(
        "[ARTIFACT] Incident events:",
        incident_path,
    )

    print(
        "[ARTIFACT] Runtime replans:",
        replan_path,
    )

    return {
        "incident_events":
            incident_path,

        "runtime_replans":
            replan_path,
    }
