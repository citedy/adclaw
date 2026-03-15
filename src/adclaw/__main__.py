# -*- coding: utf-8 -*-
"""Allow running AdClaw via ``python -m adclaw``."""
from .cli.main import cli

if __name__ == "__main__":
    cli()  # pylint: disable=no-value-for-parameter
