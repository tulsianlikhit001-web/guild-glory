#!/usr/bin/env python3
"""Idempotent patcher. Run once: python patch_ffapi.py"""
from pathlib import Path
import sys

p = Path("ffapi.py")
if not p.exists():
    sys.exit("ffapi.py not found in repo root")

src = p.read_text()
if "def api_generate(" in src:
    print("already patched")
    sys.exit(0)

pairs = [
    (
        "signal.signal(signal.SIGINT, shutdown_handler)\n"
        "signal.signal(signal.SIGTERM, shutdown_handler)",
        "for _sig in (signal.SIGINT, signal.SIGTERM):\n"
        "    try:\n"
        "        signal.signal(_sig, shutdown_handler)\n"
        "    except ValueError:\n"
        "        pass",
    ),
    (
        "\n_bootstrap_dependencies()\n",
        '\nif not os.environ.get("FFAPI_NO_BOOTSTRAP"):\n    _bootstrap_dependencies()\n',
    ),
    (
        "ROOT_DIR = os.path.dirname(os.path.abspath(__file__))",
        'ROOT_DIR = os.environ.get("FFAPI_HOME") or '
        "os.path.dirname(os.path.abspath(__file__))",
    ),
]

for old, new in pairs:
    if old not in src:
        sys.exit(f"anchor missing:\n{old[:60]}")
    src = src.replace(old, new, 1)

src += '''

def api_generate(region="IND", prefix="BOT", digits=5):
    """Importable entry point for the runner. Returns dict or None."""
    global QUIET, EXIT_FLAG
    QUIET, EXIT_FLAG = True, False
    for _ in range(3):
        acc = create_account(region=region, name_prefix=prefix, digits=digits,
                             plain=False, out_dir=None, fast_mode=True)
        if acc:
            return acc
        time.sleep(1.5)
    return None
'''

p.write_text(src)
print("ffapi.py patched")
