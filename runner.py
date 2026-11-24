#!/usr/bin/env python3
import os, sys, time, threading
import requests, yaml

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)

from ffguildbot.accounts import ApiProvider, ensure_account, pool_count, pool_fill
from ffguildbot.device import Device, FlowError
from ffguildbot.flow_join import join_guild, wait_approved, leave_guild
from ffguildbot.flow_match import run_match

CTRL = os.environ["CONTROL_URL"].rstrip("/")
TOK = os.environ["RUNNER_TOKEN"]
HDR = {"X-Runner-Token": TOK}
SERIALS = [s.strip() for s in os.environ["ADB_SERIALS"].split(",") if s.strip()]
REGION = os.environ.get("FF_REGION", "IND")
MIN_LEVEL = int(os.environ.get("BOT_MIN_LEVEL", 8))

CFG = yaml.safe_load(open(os.path.join(ROOT, "config.yaml")))
CFG["guild"]["require_level"] = MIN_LEVEL
LOCKS = {s: threading.Lock() for s in SERIALS}


def log(job_id, line):
    print(line, flush=True)
    try:
        requests.post(f"{CTRL}/api/job/{job_id}/log", headers=HDR,
                      json={"line": line}, timeout=10)
    except requests.RequestException:
        pass


def free_devices():
    return [s for s in SERIALS if not LOCKS[s].locked()]


def heartbeat():
    while True:
        try:
            requests.post(f"{CTRL}/api/heartbeat", headers=HDR,
                          json={"devices": len(SERIALS),
                                "free": len(free_devices())}, timeout=10)
        except requests.RequestException:
            pass
        time.sleep(60)


def warmer():
    target = CFG["accounts"]["pool_target"]
    while True:
        if pool_count() < CFG["accounts"]["pool_low_water"]:
            try:
                pool_fill(REGION, target)
            except Exception as e:
                print(f"warmer error {e}", flush=True)
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
            if state == "pending":
                log(job["id"], f"{serial}: pending approval")
                state = wait_approved(dev, CFG, job["guild"])
            if state not in ("joined", "already"):
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
            try:
                leave_guild(dev)
            except FlowError:
                pass
        except FlowError as e:
            outcome = str(e)
        return {"serial": serial, "matches": matches, "outcome": outcome}


def post_result(job_id, serial):
    try:
        r = run_bot(job_id and job_id, serial)
    except Exception as e:
        r = {"serial": serial, "matches": 0, "outcome": f"crash {e}"}
    try:
        requests.post(f"{CTRL}/api/job/{job_id}/result", headers=HDR,
                      json=r, timeout=20)
    except requests.RequestException:
        pass


def main():
    threading.Thread(target=heartbeat, daemon=True).start()
    threading.Thread(target=warmer, daemon=True).start()
    print(f"runner up: {len(SERIALS)} devices", flush=True)

    while True:
        try:
            job = requests.get(f"{CTRL}/api/next-job", headers=HDR,
                               timeout=20).json().get("job")
        except requests.RequestException:
            time.sleep(15)
            continue
        if not job:
            time.sleep(10)
            continue

        targets = free_devices()[: job["bots"]]
        if not targets:
            log(job["id"], "no free devices, waiting")
            time.sleep(30)
            continue

        log(job["id"], f"starting {len(targets)} bots for {job['hours']}h")
        threads = []
        for s in targets:
            t = threading.Thread(target=post_result, args=(job["id"], s))
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
        log(job["id"], "job finished")


if __name__ == "__main__":
    main()
