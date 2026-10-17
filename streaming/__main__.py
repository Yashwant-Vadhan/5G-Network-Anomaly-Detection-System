"""CLI entrypoint for running the 5G-NADS streaming server module (T11-019)."""

from __future__ import annotations

import sys

from streaming.server import main

if __name__ == "__main__":
    sys.exit(main())
