import os, sys, json, time, uuid
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import ffapi

from .device import FlowError
from .vision import tap_if, wait_for, exists, read_int
from .flow_match import run_match

LEDGER = Path("state/accounts.jsonl")
POOL = Path("state/pool.jsonl")
LEDGER.parent.mkdir(parents=True, exist_ok=True)


class Account:
    def __init__(self, serial, uid, pw, account_id, region):
        self.id = uuid.uuid4().hex[:10]
        self.serial, self.uid, self.pw = serial, uid, pw
        self.account_id, self.region = account_id, region
        self.level, self.state = 0, "new"

    def to_dict(self):
        return self.__dict__


def _record(acct, note=""):
    with LEDGER.open("a") as f:
        f.write(json.dumps({**acct.to_dict(), "note": note}) + "\n")


def pool_count():
    if not POOL.exists():
        return 0
    return len([l for l in POOL.read_text().splitlines() if l.strip()])


def pool_take():
    if not POOL.exists():
        return None
    lines = [l for l in POOL.read_text().splitlines() if l.strip()]
    if not lines:
        return None
    POOL.write_text("\n".join(lines[1:]) + "\n")
    return json.loads(lines[0])


def pool_fill(region, target):
    """Blocking top-up used by scripts/warm.py."""
    while pool_count() < target:
        raw = ffapi.api_generate(region=region)
        if not raw:
            time.sleep(3)
            continue
        with POOL.open("a") as f:
            f.write(json.dumps({"uid": raw["uid"], "password": raw["password"],
                                "account_id": raw.get("account_id", "")}) + "\n")
        print(f"pool +1 -> {pool_count()}/{target}", flush=True)


class ApiProvider:
    def create(self, dev, region="IND"):
        raw = pool_take()
        if raw is None:
            raw = ffapi.api_generate(region=region)
        if not raw:
            raise FlowError("generator returned no account")
        acct = Account(dev.serial, raw["uid"], raw["password"],
                       raw.get("account_id", ""), region)
        _record(acct, "acquired")
        return acct

    def login(self, dev, acct):
        dev.ensure_foreground()
        if exists(dev, "hud_lobby_ready", conf=0.85):
            return True
        if not tap_if(dev, "btn_login_guest", timeout=40):
            return False
        time.sleep(1.5)
        if not tap_if(dev, "btn_guest_recover", timeout=12):
            return False
        if not tap_if(dev, "field_guest_uid", timeout=12):
            return False
        dev.text(acct.uid)
        tap_if(dev, "btn_guest_next", timeout=8)
        time.sleep(1.2)
        if not tap_if(dev, "field_guest_pw", timeout=12):
            return False
        dev.text(acct.pw)
        tap_if(dev, "btn_guest_confirm", timeout=8)
        return bool(wait_for(dev, "hud_lobby_ready", timeout=90, conf=0.82))

    def validate(self, dev):
        dev.ensure_foreground()
        try:
            return read_int(dev.shot(), (0.02, 0.02, 0.28, 0.09))
        except Exception:
            return None


def ensure_account(dev, provider, region, min_level, cfg, log=print):
    acct = provider.create(dev, region)
    if not provider.login(dev, acct):
        _record(acct, "login-failed")
        raise FlowError("login failed")

    acct.level = provider.validate(dev) or 0
    log(f"account {acct.account_id} level {acct.level}")

    tries = 0
    while acct.level < min_level and tries < cfg["accounts"]["warmup_max_matches"]:
        run_match(dev, cfg)
        tries += 1
        acct.level = provider.validate(dev) or acct.level
        log(f"warmup {tries} -> level {acct.level}")

    if acct.level < min_level:
        _record(acct, f"under-levelled:{acct.level}")
        raise FlowError(f"level {acct.level} < {min_level}")

    _record(acct, "ready")
    return acct
