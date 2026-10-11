"""Put tests/ on sys.path so shared helpers (fakes.py) import from any sub-folder."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
