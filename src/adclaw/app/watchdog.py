# -*- coding: utf-8 -*-
"""Agent watchdog — monitors runner health and auto-restarts on crash."""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)


class AgentWatchdog:
    """Periodically checks runner health and attempts restart if unhealthy."""

    def __init__(self, runner, check_interval: float = 60.0, max_restarts: int = 5):
        self.runner = runner
        self.check_interval = check_interval
        self.max_restarts = max_restarts
        self._running = False
        self.restart_count = 0
        self.last_check: float = 0
        self.last_restart: float = 0

    def is_healthy(self) -> bool:
        """Return False if runner is None or has no session handler."""
        if self.runner is None:
            return False
        # Runner is healthy if it has a session object (set by init_handler).
        # memory_manager may be None when optional deps are missing — that's OK.
        return hasattr(self.runner, "session") and self.runner.session is not None

    def get_status(self) -> dict:
        """Return current watchdog status."""
        return {
            "healthy": self.is_healthy(),
            "restart_count": self.restart_count,
            "max_restarts": self.max_restarts,
            "last_check": self.last_check,
            "last_restart": self.last_restart,
            "check_interval": self.check_interval,
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
