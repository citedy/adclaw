# -*- coding: utf-8 -*-
"""Agent watchdog — monitors runner health and auto-restarts on crash.

Also provides a per-session error tracker that detects sessions stuck in
error loops so the channel layer can short-circuit instead of retrying.
"""

import asyncio
import logging
import time
from collections import defaultdict

logger = logging.getLogger(__name__)


class SessionErrorTracker:
    """Track consecutive errors per session to detect crash loops.

    When a session exceeds ``max_consecutive`` failures, it is marked as
    "tripped".  The channel layer can check ``is_tripped()`` and send an
    error message instead of hitting the agent pipeline again.

    Sessions auto-recover after ``cooldown_seconds`` or on explicit reset.
    """

    def __init__(self, max_consecutive: int = 3, cooldown_seconds: float = 120.0):
        self.max_consecutive = max_consecutive
        self.cooldown = cooldown_seconds
        self._failures: dict[str, int] = defaultdict(int)
        self._tripped_at: dict[str, float] = {}

    def record_failure(self, session_id: str) -> None:
        self._failures[session_id] += 1
        if self._failures[session_id] >= self.max_consecutive:
            if session_id not in self._tripped_at:
                logger.warning(
                    "Session %s tripped after %d consecutive failures",
                    session_id,
                    self._failures[session_id],
                )
            self._tripped_at[session_id] = time.time()

    def record_success(self, session_id: str) -> None:
        self._failures.pop(session_id, None)
        self._tripped_at.pop(session_id, None)

    def is_tripped(self, session_id: str) -> bool:
        tripped_time = self._tripped_at.get(session_id)
        if tripped_time is None:
            return False
        if time.time() - tripped_time > self.cooldown:
            # Cooldown expired — allow one probe
            self._tripped_at.pop(session_id, None)
            self._failures.pop(session_id, None)
            logger.info("Session %s cooldown expired, allowing retry", session_id)
            return False
        return True

    def reset(self, session_id: str) -> None:
        """Reset error state for a session.

        Also resets any persona-scoped variants (e.g. "persona::session_id")
        since force_clear may be called with the raw key while errors are
        recorded under the scoped key.
        """
        self._failures.pop(session_id, None)
        self._tripped_at.pop(session_id, None)
        # Also clear persona-scoped keys containing this session_id
        scoped_keys = [
            k for k in list(self._failures)
            if k.endswith(f"::{session_id}")
        ]
        for k in scoped_keys:
            self._failures.pop(k, None)
            self._tripped_at.pop(k, None)

    def get_tripped_sessions(self) -> list[str]:
        now = time.time()
        return [
            sid for sid, ts in list(self._tripped_at.items())
            if now - ts <= self.cooldown
        ]


class AgentWatchdog:
    """Periodically checks runner health and attempts restart if unhealthy."""

    def __init__(
        self,
        runner,
        check_interval: float = 60.0,
        max_restarts: int = 5,
        error_tracker: SessionErrorTracker | None = None,
    ):
        self.runner = runner
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self._running = False
        self.restart_count = 0
        self.last_check: float = 0
        self.last_restart: float = 0
        self.error_tracker = error_tracker or SessionErrorTracker()

    def is_healthy(self) -> bool:
        """Return False if runner is None or has no session handler."""
        if self.runner is None:
            return False
        # Runner is healthy if it has a session object (set by init_handler).
        # memory_manager may be None when optional deps are missing — that's OK.
        return hasattr(self.runner, "session") and self.runner.session is not None

    def get_status(self) -> dict:
        """Return current watchdog status."""
        tripped = self.error_tracker.get_tripped_sessions()
        return {
            "healthy": self.is_healthy(),
            "restart_count": self.restart_count,
            "max_restarts": self.max_restarts,
            "last_check": self.last_check,
            "last_restart": self.last_restart,
            "check_interval": self.check_interval,
            "tripped_sessions": tripped,
            "tripped_count": len(tripped),
        }

    async def _try_restart(self) -> bool:
        """Attempt to restart the runner. Returns True on success."""
        self.last_restart = time.time()
        logger.warning(
            "Watchdog: attempting restart %d/%d",
            self.restart_count + 1,
            self.max_restarts,
        )
        try:
            # Close existing memory_manager if present
            mm = getattr(self.runner, "memory_manager", None)
            if mm is not None:
                try:
                    await mm.close()
                except Exception:
                    pass
                self.runner.memory_manager = None

            await self.runner.init_handler()

            if self.is_healthy():
                self.restart_count = 0
                logger.info("Watchdog: restart succeeded, runner is healthy")
                return True

            self.restart_count += 1
            logger.warning("Watchdog: restart completed but runner still unhealthy")
            return False
        except Exception:
            self.restart_count += 1
            logger.exception("Watchdog: restart attempt failed")
            return False

    async def start(self) -> None:
        """Run the watchdog loop."""
        self._running = True
        logger.info(
            "Watchdog started (interval=%.1fs, max_restarts=%d)",
            self.check_interval,
            self.max_restarts,
        )
        while self._running:
            await asyncio.sleep(self.check_interval)
            if not self._running:
                break
            self.last_check = time.time()
            if not self.is_healthy():
                if self.restart_count < self.max_restarts:
                    await self._try_restart()
                else:
                    logger.error(
                        "Watchdog: max restarts (%d) reached, not retrying",
                        self.max_restarts,
                    )

    def stop(self) -> None:
        """Signal the watchdog loop to stop."""
        self._running = False
        logger.info("Watchdog stopped")
