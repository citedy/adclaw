# -*- coding: utf-8 -*-
"""Safe JSON session with filename sanitization and corruption protection.

Windows filenames cannot contain: \\ / : * ? " < > |
This module wraps agentscope's JSONSession so that session_id and user_id
are sanitized before being used as filenames.

Additionally, it protects against corrupted session files by:
- Using atomic writes (write to temp file, then rename) to prevent
  partial/truncated JSON on crash or power loss.
- Catching JSONDecodeError on load: backs up the corrupted file and
  starts a fresh session instead of crashing.
"""
import json
import logging
import os
import re
import tempfile
from datetime import datetime, timezone

from agentscope.session import JSONSession
from agentscope.module import StateModule

logger = logging.getLogger(__name__)

# Characters forbidden in Windows filenames
_UNSAFE_FILENAME_RE = re.compile(r'[\\/:*?"<>|]')


def sanitize_filename(name: str) -> str:
    """Replace characters that are illegal in Windows filenames with ``--``.

    >>> sanitize_filename('discord:dm:12345')
    'discord--dm--12345'
    >>> sanitize_filename('normal-name')
    'normal-name'
    """
    return _UNSAFE_FILENAME_RE.sub("--", name)


class SafeJSONSession(JSONSession):
    """JSONSession subclass with safe filenames, atomic saves and
    corruption-resilient loads.
    """

    def _get_save_path(self, session_id: str, user_id: str) -> str:
        """Return a filesystem-safe save path."""
        os.makedirs(self.save_dir, exist_ok=True)
        safe_sid = sanitize_filename(session_id)
        safe_uid = sanitize_filename(user_id) if user_id else ""
        if safe_uid:
            file_path = f"{safe_uid}_{safe_sid}.json"
        else:
            file_path = f"{safe_sid}.json"
        return os.path.join(self.save_dir, file_path)

    async def save_session_state(
        self,
        session_id: str,
        user_id: str = "",
        **state_modules_mapping: StateModule,
    ) -> None:
        """Atomically save session state to prevent corruption.

        Writes to a temporary file first, then renames it over the
        target path.  On POSIX systems ``os.replace`` is atomic,
        so a crash mid-write cannot leave a truncated JSON file.
        """
        state_dicts = {
            name: state_module.state_dict()
            for name, state_module in state_modules_mapping.items()
        }
        save_path = self._get_save_path(session_id, user_id=user_id)
        save_dir = os.path.dirname(save_path)

        fd, tmp_path = tempfile.mkstemp(
            dir=save_dir, suffix=".tmp", prefix=".session_"
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(state_dicts, f, ensure_ascii=False)
            os.replace(tmp_path, save_path)
        except BaseException:
            # Clean up temp file on any failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise

    async def load_session_state(
        self,
        session_id: str,
        user_id: str = "",
        allow_not_exist: bool = True,
        **state_modules_mapping: StateModule,
    ) -> None:
        """Load session state with corruption protection.

        If the session file exists but contains invalid JSON, it is
        renamed to ``<name>.corrupted.<timestamp>`` and a fresh
        (empty) session is started instead of crashing.
        """
        save_path = self._get_save_path(session_id, user_id=user_id)

        if not os.path.exists(save_path):
            if allow_not_exist:
                logger.info(
                    "Session file %s does not exist. Starting fresh.",
                    save_path,
                )
                return
            raise ValueError(
                f"Session file {save_path} does not exist.",
            )

        try:
            with open(save_path, "r", encoding="utf-8", errors="surrogatepass") as f:
                states = json.load(f)
        except (json.JSONDecodeError, UnicodeDecodeError, OSError) as exc:
            # Back up the corrupted file so it can be inspected later
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
            backup_path = f"{save_path}.corrupted.{ts}"
            try:
                os.rename(save_path, backup_path)
                logger.warning(
                    "Corrupted session file detected: %s — "
                    "backed up to %s and starting fresh session. "
                    "Error: %s",
                    save_path,
                    backup_path,
                    exc,
                )
            except OSError as rename_err:
                logger.warning(
                    "Corrupted session file %s could not be backed up "
                    "(%s). Starting fresh session. Original error: %s",
                    save_path,
                    rename_err,
                    exc,
                )
            return

        failed_modules = []
        for name, state_module in state_modules_mapping.items():
            if name in states:
                try:
                    state_module.load_state_dict(states[name])
                except Exception as load_err:
                    failed_modules.append(name)
                    logger.warning(
                        "Failed to restore state for module '%s' in %s: %s. "
                        "Module will start with fresh state.",
                        name,
                        save_path,
                        load_err,
                    )
        if failed_modules:
            logger.warning(
                "Session %s loaded with %d module(s) reset: %s",
                save_path,
                len(failed_modules),
                ", ".join(failed_modules),
            )
        else:
            logger.info(
                "Loaded session state from %s successfully.",
                save_path,
            )
