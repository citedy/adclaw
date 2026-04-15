# -*- coding: utf-8 -*-
"""Channel registry: built-in + custom channels from working dir.

Optional channels (discord, dingtalk, feishu) gracefully degrade when the
corresponding SDK is not installed. This keeps the core image lean while
still allowing users to install extras later (``pip install adclaw[discord]``).
"""
from __future__ import annotations

import importlib
import logging
import sys
from typing import TYPE_CHECKING

from ...constant import CUSTOM_CHANNELS_DIR
from .base import BaseChannel
from .console import ConsoleChannel
from .imessage import IMessageChannel
from .qq import QQChannel
from .telegram import TelegramChannel

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

_BUILTIN: dict[str, type[BaseChannel]] = {
    "imessage": IMessageChannel,
    "qq": QQChannel,
    "telegram": TelegramChannel,
    "console": ConsoleChannel,
}

# Optional channels that require extras: adclaw[discord], adclaw[dingtalk], adclaw[feishu]
_OPTIONAL_CHANNELS: dict[str, tuple[str, str]] = {
    "discord": (".discord_", "DiscordChannel"),
    "dingtalk": (".dingtalk", "DingTalkChannel"),
    "feishu": (".feishu", "FeishuChannel"),
}

# Track which optional channels are not installed (so manager.from_config
# can log a clear warning when user enables one without the SDK).
_MISSING_OPTIONAL_CHANNELS: set[str] = set()

for _key, (_module, _cls) in _OPTIONAL_CHANNELS.items():
    try:
        _mod = importlib.import_module(_module, package=__package__)
        _BUILTIN[_key] = getattr(_mod, _cls)
    except ImportError as exc:
        _MISSING_OPTIONAL_CHANNELS.add(_key)
        logger.info(
            "Optional channel %s not available (install with: pip install adclaw[%s]): %s",
            _key, _key, exc,
        )


def _discover_custom_channels() -> dict[str, type[BaseChannel]]:
    """Load channel classes from CUSTOM_CHANNELS_DIR."""
    out: dict[str, type[BaseChannel]] = {}
    if not CUSTOM_CHANNELS_DIR.is_dir():
        return out

    dir_str = str(CUSTOM_CHANNELS_DIR)
    if dir_str not in sys.path:
        sys.path.insert(0, dir_str)

    for path in sorted(CUSTOM_CHANNELS_DIR.iterdir()):
        if path.suffix == ".py" and path.stem != "__init__":
            name = path.stem
        elif path.is_dir() and (path / "__init__.py").exists():
            name = path.name
        else:
            continue
        try:
            mod = importlib.import_module(name)
        except Exception:
            logger.exception("failed to load custom channel: %s", name)
            continue
        for obj in vars(mod).values():
            if (
                isinstance(obj, type)
                and issubclass(obj, BaseChannel)
                and obj is not BaseChannel
            ):
                key = getattr(obj, "channel", None)
                if key:
                    out[key] = obj
                    logger.debug("custom channel registered: %s", key)
    return out


# Logical set of built-in channel keys — always includes optional channels
# regardless of whether their SDKs are installed. This is used by the CLI
# (`adclaw channels install/remove`) to correctly classify built-in vs custom.
# Without this, installing "discord" on a core image would write a stub to
# custom_channels/discord.py that would later shadow the real built-in class
# when `pip install adclaw[discord]` is run.
BUILTIN_CHANNEL_KEYS: frozenset[str] = frozenset(
    set(_BUILTIN.keys()) | set(_OPTIONAL_CHANNELS.keys())
)


def get_channel_registry() -> dict[str, type[BaseChannel]]:
    """Built-in channel classes + custom channels from custom_channels/."""
    out = dict(_BUILTIN)
    out.update(_discover_custom_channels())
    return out
