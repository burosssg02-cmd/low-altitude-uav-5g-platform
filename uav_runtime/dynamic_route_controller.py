import asyncio
from copy import deepcopy


class DynamicRouteController:
    """
    Owns the mutable remaining route during flight.

    The current PX4 command is NOT modified here.
    A validated replacement route is first stored
    as pending, then the mission executor decides
    when to apply it.
    """

    def __init__(
        self,
        initial_waypoints: list[dict],
    ):
        if not initial_waypoints:
            raise ValueError(
                "initial_waypoints must not be empty"
            )

        self._remaining = deepcopy(
            initial_waypoints
        )

        self._pending = None
        self._pending_reason = None

        self.replan_event = asyncio.Event()

        self.requested_replans = 0
        self.applied_replans = 0

    @property
    def remaining_count(self) -> int:
        return len(
            self._remaining
        )

    @property
    def has_pending_replan(self) -> bool:
        return self._pending is not None

    def pop_next(self) -> dict | None:
        if not self._remaining:
            return None

        return self._remaining.pop(0)

    def request_replan(
        self,
        new_waypoints: list[dict],
        reason: str,
    ) -> bool:
        """
        Queue one validated replacement route.

        Duplicate requests are rejected while another
        replacement is still waiting to be applied.
        """

        if not new_waypoints:
            raise ValueError(
                "new_waypoints must not be empty"
            )

        if self._pending is not None:
            return False

        self._pending = deepcopy(
            new_waypoints
        )

        self._pending_reason = (
            reason.strip()
            or "runtime replan"
        )

        self.requested_replans += 1

        self.replan_event.set()

        return True

    def apply_pending_replan(
        self,
    ) -> dict | None:
        """
        Replace all unexecuted waypoints with the
        pending validated route.
        """

        if self._pending is None:
            return None

        new_route = self._pending

        metadata = {
            "reason":
                self._pending_reason,

            "waypoint_count":
                len(new_route),

            "replan_index":
                self.applied_replans + 1,
        }

        self._remaining = deepcopy(
            new_route
        )

        self._pending = None
        self._pending_reason = None

        self.applied_replans += 1

        self.replan_event.clear()

        return metadata

    def cancel_pending_replan(
        self,
    ) -> bool:
        if self._pending is None:
            return False

        self._pending = None
        self._pending_reason = None

        self.replan_event.clear()

        return True

    def snapshot(self) -> dict:
        return {
            "remaining":
                deepcopy(
                    self._remaining
                ),

            "remaining_count":
                self.remaining_count,

            "has_pending_replan":
                self.has_pending_replan,

            "requested_replans":
                self.requested_replans,

            "applied_replans":
                self.applied_replans,
        }
