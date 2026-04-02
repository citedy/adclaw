# -*- coding: utf-8 -*-
"""Tests for crash resilience: SessionErrorTracker, defensive session loading,
auto-recovery in runner, and _is_session_state_error classification."""

import json
import time

import pytest
from unittest.mock import MagicMock


# ---------------------------------------------------------------------------
# SessionErrorTracker
# ---------------------------------------------------------------------------

class TestSessionErrorTracker:
    def test_no_failures_not_tripped(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=3)
        assert tracker.is_tripped("session-1") is False

    def test_below_threshold_not_tripped(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=3)
        tracker.record_failure("session-1")
        tracker.record_failure("session-1")
        assert tracker.is_tripped("session-1") is False

    def test_at_threshold_tripped(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=3)
        for _ in range(3):
            tracker.record_failure("session-1")
        assert tracker.is_tripped("session-1") is True

    def test_success_resets_counter(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=3)
        tracker.record_failure("session-1")
        tracker.record_failure("session-1")
        tracker.record_success("session-1")
        tracker.record_failure("session-1")
        assert tracker.is_tripped("session-1") is False

    def test_cooldown_untrips(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=2, cooldown_seconds=0.1)
        tracker.record_failure("s1")
        tracker.record_failure("s1")
        assert tracker.is_tripped("s1") is True
        time.sleep(0.15)
        assert tracker.is_tripped("s1") is False

    def test_reset_clears_state(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=2)
        tracker.record_failure("s1")
        tracker.record_failure("s1")
        assert tracker.is_tripped("s1") is True
        tracker.reset("s1")
        assert tracker.is_tripped("s1") is False

    def test_isolation_between_sessions(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=2)
        tracker.record_failure("s1")
        tracker.record_failure("s1")
        assert tracker.is_tripped("s1") is True
        assert tracker.is_tripped("s2") is False

    def test_get_tripped_sessions(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=1)
        tracker.record_failure("s1")
        tracker.record_failure("s2")
        tripped = tracker.get_tripped_sessions()
        assert set(tripped) == {"s1", "s2"}

    def test_get_tripped_excludes_expired(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=1, cooldown_seconds=0.05)
        tracker.record_failure("s1")
        time.sleep(0.1)
        assert tracker.get_tripped_sessions() == []

    def test_reset_clears_persona_scoped_keys(self):
        from adclaw.app.watchdog import SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=1)
        # Errors recorded under persona-scoped key
        tracker.record_failure("default::chat123")
        assert tracker.is_tripped("default::chat123") is True
        # Reset called with raw key (as force_clear does)
        tracker.reset("chat123")
        assert tracker.is_tripped("default::chat123") is False


# ---------------------------------------------------------------------------
# Watchdog integration with SessionErrorTracker
# ---------------------------------------------------------------------------

class TestWatchdogWithTracker:
    def test_status_includes_tripped(self):
        from adclaw.app.watchdog import AgentWatchdog, SessionErrorTracker
        tracker = SessionErrorTracker(max_consecutive=1)
        tracker.record_failure("session-x")
        runner = MagicMock()
        wd = AgentWatchdog(runner=runner, error_tracker=tracker)
        status = wd.get_status()
        assert "tripped_sessions" in status
        assert "session-x" in status["tripped_sessions"]
        assert status["tripped_count"] == 1

    def test_status_empty_when_no_trips(self):
        from adclaw.app.watchdog import AgentWatchdog, SessionErrorTracker
        tracker = SessionErrorTracker()
        runner = MagicMock()
        wd = AgentWatchdog(runner=runner, error_tracker=tracker)
        status = wd.get_status()
        assert status["tripped_count"] == 0


# ---------------------------------------------------------------------------
# Defensive session loading (session.py)
# ---------------------------------------------------------------------------

class TestDefensiveSessionLoading:
    @pytest.mark.asyncio
    async def test_load_state_dict_failure_recovers(self, tmp_path):
        """If load_state_dict throws, session should start with fresh state."""
        from adclaw.app.runner.session import SafeJSONSession

        session = SafeJSONSession(save_dir=str(tmp_path))

        # Create a valid JSON session file
        session_data = {"agent": {"some": "corrupt_data"}}
        save_path = tmp_path / "test_session.json"
        save_path.write_text(json.dumps(session_data))

        # Create a mock state module that crashes on load
        broken_module = MagicMock()
        broken_module.load_state_dict.side_effect = ValueError(
            "Invalid image URL: file:///missing.jpg"
        )

        # Should NOT raise — should log warning and continue
        await session.load_session_state(
            session_id="test_session",
            user_id="",
            agent=broken_module,
        )
        # Module was called with the state dict
        broken_module.load_state_dict.assert_called_once()

    @pytest.mark.asyncio
    async def test_load_state_dict_success(self, tmp_path):
        """Normal load_state_dict should work as before."""
        from adclaw.app.runner.session import SafeJSONSession

        session = SafeJSONSession(save_dir=str(tmp_path))

        state_data = {"agent": {"memory": {"messages": []}}}
        save_path = tmp_path / "ok_session.json"
        save_path.write_text(json.dumps(state_data))

        ok_module = MagicMock()
        await session.load_session_state(
            session_id="ok_session",
            user_id="",
            agent=ok_module,
        )
        ok_module.load_state_dict.assert_called_once_with(state_data["agent"])

    @pytest.mark.asyncio
    async def test_corrupt_json_backed_up(self, tmp_path):
        """Corrupt JSON should be backed up, not crash."""
        from adclaw.app.runner.session import SafeJSONSession

        session = SafeJSONSession(save_dir=str(tmp_path))
        save_path = tmp_path / "corrupt_session.json"
        save_path.write_text("{invalid json!!!}")

        ok_module = MagicMock()
        # Should NOT raise
        await session.load_session_state(
            session_id="corrupt_session",
            user_id="",
            agent=ok_module,
        )
        # Module should NOT be called (no valid state)
        ok_module.load_state_dict.assert_not_called()
        # Backup should exist
        backups = list(tmp_path.glob("*.corrupted.*"))
        assert len(backups) == 1


# ---------------------------------------------------------------------------
# _is_session_state_error classification
# ---------------------------------------------------------------------------

class TestIsSessionStateError:
    def test_valueerror_from_formatter(self):
        from adclaw.app.runner.runner import _is_session_state_error

        try:
            # Simulate the exact error from the incident
            def fake_formatter():
                raise ValueError("Invalid image URL: file:///missing.jpg")
            fake_formatter()
        except ValueError as e:
            assert _is_session_state_error(e) is True

    def test_keyerror_from_unrelated_code(self):
        from adclaw.app.runner.runner import _is_session_state_error

        try:
            def user_tool_handler():
                raise KeyError("missing_field")
            user_tool_handler()
        except KeyError as e:
            # KeyError without session markers in traceback → False
            assert _is_session_state_error(e) is False

    def test_connection_error_not_session(self):
        from adclaw.app.runner.runner import _is_session_state_error

        try:
            raise ConnectionError("refused")
        except ConnectionError as e:
            assert _is_session_state_error(e) is False

    def test_runtime_error_not_session(self):
        from adclaw.app.runner.runner import _is_session_state_error

        try:
            raise RuntimeError("something else")
        except RuntimeError as e:
            assert _is_session_state_error(e) is False

    def test_valueerror_with_compaction_marker(self):
        from adclaw.app.runner.runner import _is_session_state_error

        try:
            def memory_compaction_hook():
                raise ValueError("bad state in compaction")
            memory_compaction_hook()
        except ValueError as e:
            assert _is_session_state_error(e) is True
