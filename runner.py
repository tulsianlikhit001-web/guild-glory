#!/usr/bin/env python3
import os, sys, time, threading, subprocess
import requests, yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ffguildbot.accounts import ApiProvider, ensure_account, pool_count, pool_fill
from ffguildbot.device import Device, FlowError
from ffguildbot.flow_join import join_guild, wait_approved, leave_guild
from ffguildbot.flow_match import run_match
from ffguildbot import vision

CTRL = os.environ["CONTROL_URL"].rstrip("/")
TOK = os.environ["RUNNER_TOKEN"]
HDR = {"X-Runner-Token": TOK}
SERIALS = [s.strip() for s in os.environ["ADB_SERIALS"].split(",") if s.strip()]
REGION = os.environ.get("FF_REGION", "IND")
MIN_LEVEL = int(os.environ.get("BOT_MIN_LEVEL", 2))
NO_LEAVE = os.environ.get("FF_NO_LEAVE") == "1"
FORCE = os.environ.get("FF_FORCE") == "1"

CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
CFG["guild"]["require_level"] = MIN_LEVEL
LOCKS = {s: threading.Lock() for s in SERIALS}
RUNNING = threading.Event()
RUNNING.set()


def log(job_id, line):
    print(line, flush=True)
    for _ in range(2):
        try:
            requests.post(f"{CTRL}/api/job/{job_id}/log", headers=HDR,
                          json={"line": line}, timeout=10)
            return
        except requests.RequestException:
            time.sleep(1)


def free_devices():
    return [s for s in SERIALS if not LOCKS[s].locked()]


def preflight():
    fatal, warn = [], []

    try:
        import ffapi  # noqa: F401
        if not hasattr(ffapi, "create_account"):
            fatal.append("ffapi imported but has no create_account()")
        if not hasattr(ffapi, "api_generate"):
            fatal.append("ffapi not patched — run: python patch_ffapi.py")
    except Exception as e:
        fatal.append(f"cannot import ffapi: {type(e).__name__}: {e} "
                     "— commit ffapi.py to repo root, then run patch_ffapi.py")

    try:
        r = requests.get(f"{CTRL}/health", timeout=15)
        if r.status_code != 200:
            fatal.append(f"control plane /health -> {r.status_code}")
    except requests.RequestException as e:
        fatal.append(f"cannot reach control plane {CTRL}: {e}")

    try:
        r = requests.get(f"{CTRL}/api/ping", headers=HDR, timeout=15)
        if r.status_code == 401:
            fatal.append("RUNNER_TOKEN rejected by control plane (401) — "
                         "runner.env does not match Render")
        elif r.status_code != 200:
            fatal.append(f"control plane /api/ping -> {r.status_code}")
    except requests.RequestException as e:
        fatal.append(f"ping failed: {e}")

    try:
        out = subprocess.run(["adb", "devices"], capture_output=True,
                             text=True, timeout=20)
        attached = [l.split("\t")[0] for l in out.stdout.splitlines()[1:]
                    if "\tdevice" in l]
        if not attached:
            fatal.append("adb sees no attached devices")
        for s in SERIALS:
            if s not in attached:
                warn.append(f"serial {s} not attached right now")
    except Exception as e:
        fatal.append(f"adb check failed: {e}")

    missing = vision.missing_required()
    if missing:
        msg = (f"{len(missing)} templates missing: {', '.join(missing[:8])}"
               f"{' …' if len(missing) > 8 else ''} — run scripts/check_templates.py")
        (warn if FORCE else fatal).append(msg)

    for m in warn:
        print(f"WARN  {m}", flush=True)
    for m in fatal:
        print(f"FATAL {m}", flush=True)
    return not fatal


def claim():
    r = requests.get(f"{CTRL}/api/next-job", headers=HDR, timeout=20)
    if r.status_code == 401:
        raise SystemExit("RUNNER_TOKEN rejected (401) — check runner.env")
    if r.status_code != 200:
        raise FlowError(f"next-job -> {r.status_code} {r.text[:120]}")
    return r.json().get("job")


def heartbeat():
    while RUNNING.is_set():
        try:
            requests.post(f"{CTRL}/api/heartbeat", headers=HDR,
                          json={"devices": len(SERIALS),
                                "free": len(free_devices()),
                                "missing_templates": len(vision.missing_required())},
                          timeout=10)
        except requests.RequestException:
            pass
        time.sleep(120)


def warmer():
    if os.environ.get("FF_NO_WARMER") == "1":
        return
    target = CFG["accounts"]["pool_target"]
    low = CFG["accounts"]["pool_low_water"]
    fails = 0
    while RUNNING.is_set():
        try:
            if pool_count() < low:
                pool_fill(REGION, target, batch=15)
                fails = 0
        except Exception as e:
            fails += 1
            print(f"warmer error {e}", flush=True)
            if fails > 20:
                print("warmer backing off 10m", flush=True)
                time.sleep(600)
                fails = 0
                continue
        time.sleep(120)


def run_bot(job, serial):
    with LOCKS[serial]:
        dev = Device(serial, CFG)
        deadline = time.time() + job["hours"] * 3600
        matches, outcome = 0, "ok"
        try:
            dev.launch()
            ensure_account(dev, ApiProvider(), REGION, MIN_LEVEL, CFG,
                           lambda m: log(job["id"], f"{serial}: {m}"))

            state = join_guild(dev, job["guild"], CFG)
            log(job["id"], f"{serial}: join state {state}")
            if state == "pending":
                state = wait_approved(dev, CFG, job["guild"])
                if state != "joined":
                    log(job["id"], f"{serial}: approval timed out, playing anyway")
            if state not in ("joined", "already", "pending"):
                raise FlowError("join failed")

            cap = CFG["session"]["max_matches_per_bot"]
            while time.time() < deadline and matches < cap:
                try:
                    r = run_match(dev, CFG)
                    matches += 1
                    log(job["id"], f"{serial}: match {matches} {r}")
                except FlowError as e:
                    log(job["id"], f"{serial}: match error {e}")
                    time.sleep(5)
                if time.time() < deadline:
                    time.sleep(CFG["session"]["between_matches_s"][0])

            if not NO_LEAVE:
                try:
                    leave_guild(dev)
                except FlowError as e:
                    log(job["id"], f"{serial}: leave error {e}")
        except FlowError as e:
            outcome = str(e)
            log(job["id"], f"{serial}: FAILED {e}")
        except Exception as e:
            outcome = f"crash {type(e).__name__}: {e}"
            log(job["id"], f"{serial}: CRASH {outcome}")
        return {"serial": serial, "matches": matches, "outcome": outcome}


def post_result(job, serial):
    try:
        r = run_bot(job, serial)
    except Exception as e:
        r = {"serial": serial, "matches": 0, "outcome": f"crash {e}"}
    for _ in range(3):
        try:
            requests.post(f"{CTRL}/api/job/{job['id']}/result", headers=HDR,
                          json=r, timeout=20)
            return
        except requests.RequestException:
            time.sleep(3)


def main():
    if not preflight():
        print("fix the FATAL lines above, then run again "
              "(FF_FORCE=1 overrides template warnings)", flush=True)
        sys.exit(1)

    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=warmer, daemon=True).start()
    print(f"runner up: {len(SERIALS)} devices, min level {MIN_LEVEL}", flush=True)

    while RUNNING.is_set():
        try:
            job = claim()
        except (requests.RequestException, ValueError, FlowError) as e:
            print(f"claim error: {e}", flush=True)
            time.sleep(15)
            continue
        if not job:
            time.sleep(30)
            continue

        log(job["id"], f"claimed: guild {job['guild']} {job['hours']}h {job['bots']} bots")

        give_up = time.time() + 900
        targets = free_devices()[: job["bots"]]
        while not targets and time.time() < give_up:
            log(job["id"], "no free devices, waiting")
            time.sleep(20)
            targets = free_devices()[: job["bots"]]
        if not targets:
            log(job["id"], "gave up waiting for a free device")
            continue

        log(job["id"], f"starting {len(targets)} bots for {job['hours']}h")
        threads = [threading.Thread(target=post_result, args=(job, s)) for s in targets]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        log(job["id"], "job finished")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        RUNNING.clear()
