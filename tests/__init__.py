# Package initializer for test modules.
#
# Makes the `mlb` package (under scripts/) importable from every test module
# without each one re-deriving the path. The CLI scripts do `from mlb import ...`,
# so the tests mirror that by putting `scripts/` on sys.path.

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"

for p in (str(ROOT), str(SCRIPTS)):
    if p not in sys.path:
        sys.path.insert(0, p)
