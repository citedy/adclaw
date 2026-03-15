import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock


@pytest.fixture
def mock_runner():
    runner = MagicMock()
    runner.init_handler = AsyncMock()
    runner.memory_manager = MagicMock()
    runner.memory_manager.close = AsyncMock()
    return runner


@pytest.mark.asyncio
async def test_watchdog_detects_healthy(mock_runner):
    from adclaw.app.watchdog import AgentWatchdog
    wd = AgentWatchdog(runner=mock_runner, check_interval=0.1)
    assert wd.is_healthy() is True


@pytest.mark.asyncio
async def test_watchdog_detects_unhealthy(mock_runner):
    from adclaw.app.watchdog import AgentWatchdog
    mock_runner.memory_manager = None
    wd = AgentWatchdog(runner=mock_runner, check_interval=0.1)
    assert wd.is_healthy() is False


@pytest.mark.asyncio
async def test_watchdog_auto_restarts(mock_runner):
    from adclaw.app.watchdog import AgentWatchdog
    mock_runner.memory_manager = None
    wd = AgentWatchdog(runner=mock_runner, check_interval=0.05, max_restarts=1)
    task = asyncio.create_task(wd.start())
    await asyncio.sleep(0.2)
    wd.stop()
    await task
    mock_runner.init_handler.assert_called()


@pytest.mark.asyncio
async def test_watchdog_respects_max_restarts(mock_runner):
    from adclaw.app.watchdog import AgentWatchdog
    mock_runner.memory_manager = None
    mock_runner.init_handler = AsyncMock(side_effect=Exception("broken"))
    wd = AgentWatchdog(runner=mock_runner, check_interval=0.05, max_restarts=2)
    task = asyncio.create_task(wd.start())
    await asyncio.sleep(0.4)
    wd.stop()
    await task
    assert wd.restart_count <= 2


@pytest.mark.asyncio
async def test_watchdog_resets_count_on_success(mock_runner):
    from adclaw.app.watchdog import AgentWatchdog
    mock_runner.memory_manager = None

    async def flaky_init():
        mock_runner.memory_manager = MagicMock()

    mock_runner.init_handler = AsyncMock(side_effect=flaky_init)
    wd = AgentWatchdog(runner=mock_runner, check_interval=0.05, max_restarts=3)
    task = asyncio.create_task(wd.start())
    await asyncio.sleep(0.3)
    wd.stop()
    await task
    assert wd.restart_count == 0


@pytest.mark.asyncio
async def test_watchdog_get_status(mock_runner):
    from adclaw.app.watchdog import AgentWatchdog
    wd = AgentWatchdog(runner=mock_runner, check_interval=60)
    status = wd.get_status()
    assert "healthy" in status
    assert "restart_count" in status
    assert "last_check" in status
