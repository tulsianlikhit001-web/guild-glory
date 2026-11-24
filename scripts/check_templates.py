#!/usr/bin/env python3
"""Report templates the code expects vs what exists. Exit 1 if any missing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from ffguildbot.vision import REQUIRED, TPL_DIR

TPL = Path(TPL_DIR)
present = {p.stem for p in TPL.glob("*.png")} if TPL.exists() else set()
missing = [n for n in REQUIRED if n not in present]
extra = sorted(present - set(REQUIRED))

for n in missing:
    print(f"MISSING  {n}")
for n in extra:
    print(f"extra    {n}")

print(f"\n{len(REQUIRED) - len(missing)}/{len(REQUIRED)} required templates present")
sys.exit(1 if missing else 0)
