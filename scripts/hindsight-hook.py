#!/usr/bin/env python3
"""Repository entry point; installed clients receive the self-contained hook modules."""
from pathlib import Path
import runpy
import sys

if __name__ == "__main__":
    source = Path(__file__).resolve().parents[1] / "apps/hindsight-session-ingest"
    sys.path.insert(0, str(source))
    runpy.run_path(str(source / "hindsight-hook.py"), run_name="__main__")
