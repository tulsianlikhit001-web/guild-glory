#!/usr/bin/env python3
import os, sys, time, threading
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


def heartbeat():
    while RUNNING.is_set():
        try:
            requests.post(f"{CTRL}/api/heartbeat", headers=HDR,
                          json={"devices": len(SERIALS),
                                "free": len(free_devices()),
                                "missing_templates": len(vision.missing())},
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
                pool_fill(REGION, target)
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
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=warmer, daemon=True).start()
    print(f"runner up: {len(SERIALS)} devices, min level {MIN_LEVEL}", flush=True)

    while RUNNING.is_set():
        try:
            job = requests.get(f"{CTRL}/api/next-job", headers=HDR,
                               timeout=20).json().get("job")
        except (requests.RequestException, ValueError):
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
