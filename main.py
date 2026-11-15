#!/usr/bin/env python3
"""Entry point for the distortion atlas: ``python3 main.py``.

Run ``python3 main.py --self-check`` for a non-graphical readout of the panel,
scale and pixel-path check. See ``README.md`` for the full key map.
"""

import sys

from visiontest.ui import main

if __name__ == "__main__":
    sys.exit(main())
