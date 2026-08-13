from __future__ import annotations

import sys
from pathlib import Path


PLATFORM_ROOT = Path(__file__).resolve().parents[1] / "platform"
if str(PLATFORM_ROOT) not in sys.path:
    sys.path.insert(0, str(PLATFORM_ROOT))
