#!/usr/bin/env python3
"""Entry point for the distortion atlas: ``python3 main.py``.

Run ``python3 main.py --self-check`` for the panel, scale and pixel-path readout
plus a checkerboard that stays on screen until a key press (``--hold 0`` for
scripted runs, ``--hold SECONDS`` for a bounded look). See ``README.md`` for the
full key map.
"""

import sys

from visiontest.ui import main

if __name__ == "__main__":
    sys.exit(main())
