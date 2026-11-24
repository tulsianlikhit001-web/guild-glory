#!/usr/bin/env python3
"""Isolate runner connectivity + token. Run from repo root: python scripts/probe.py"""
import os, subprocess, sys, urllib.request, urllib.error
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))


def load_env():
    p = ROOT / "runner.env"
    if not p.exists():
        sys.exit(f"missing {p} — copy runner.env.example to runner.env and fill it")
    for line in p.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        os.environ.setdefault(k.strip(), v.strip().strip('"').strip("'"))


def hit(path, token=None):
    url = os.environ["CONTROL_URL"].rstrip("/") + path
    req = urllib.request.Request(url)
    if token:
        req.add_header("X-Runner-Token", token)
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read()[:160].decode(errors="ignore")
    except urllib.error.HTTPError as e:
        return e.code, e.read()[:160].decode(errors="ignore")
    except Exception as e:
        return None, f"{type(e).__name__}: {e}"


def main():
    load_env()
    fails = 0

    print(f"control: {os.environ.get('CONTROL_URL')}")
    print(f"token:   {len(os.environ.get('RUNNER_TOKEN', ''))} chars")

    s, b = hit("/health")
    print(f"health   -> {s} {b[:80]}")
    fails += s != 200

    s, b = hit("/api/ping", os.environ.get("RUNNER_TOKEN"))
    if s == 200:
        print(f"token    -> OK {b[:80]}")
    else:
        print(f"token    -> FAIL {s} {b[:120]}")
        fails += 1

    try:
        import ffapi
        print("ffapi    -> importable" if hasattr(ffapi, "api_generate")
              else "ffapi    -> imported but NOT patched (run patch_ffapi.py)")
        fails += not hasattr(ffapi, "api_generate")
    except Exception as e:
        print(f"ffapi    -> FAIL {type(e).__name__}: {e}")
        fails += 1

    try:
        out = subprocess.run(["adb", "devices"], capture_output=True, text=True,
                             timeout=20)
        devs = [l.split("\t")[0] for l in out.stdout.splitlines()[1:] if "\tdevice" in l]
        print(f"adb      -> {len(devs)} device(s): {', '.join(devs) or 'none'}")
        fails += not devs
    except Exception as e:
        print(f"adb      -> FAIL {e}")
        fails += 1

    from ffguildbot.vision import missing_required
    miss = missing_required()
    print(f"templates-> {len(miss)} missing")
    fails += bool(miss)

    print("\n" + ("ALL CLEAR — run: python runner.py" if not fails
                  else f"{fails} problem(s) above"))


if __name__ == "__main__":
    main()
