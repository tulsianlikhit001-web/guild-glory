import os, sys, json, time, uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
import ffapi

from .device import FlowError
from .vision import TPL_DIR, tap_if, wait_for, exists, find, read_int
from .flow_match import run_match

STATE = ROOT / "state"
STATE.mkdir(parents=True, exist_ok=True)
LEDGER = STATE / "accounts.jsonl"
POOL = STATE / "pool.jsonl"

WARM_RANKS = ("rank_gold", "rank_platinum", "rank_diamond",
              "rank_heroic", "rank_grandmaster")


class Account:
    def __init__(self, serial, uid, pw, account_id, region):
        self.id = uuid.uuid4().hex[:10]
        self.serial, self.uid, self.pw = serial, uid, pw
        self.account_id, self.region = account_id, region
        self.level, self.state = 0, "new"

    def to_dict(self):
        return self.__dict__


def _record(acct, note=""):
    try:
        with LEDGER.open("a") as f:
            f.write(json.dumps({**acct.to_dict(), "note": note}) + "\n")
    except OSError:
        pass


def _has_tpl(name):
    return os.path.exists(os.path.join(TPL_DIR, name + ".png"))


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
    POOL.write_text("\n".join(lines[1:]) + ("\n" if len(lines) > 1 else ""))
    try:
        return json.loads(lines[0])
    except json.JSONDecodeError:
        return pool_take()


def pool_fill(region, target, batch=10):
    added = 0
    while pool_count() < target and added < batch:
        raw = ffapi.api_generate(region=region)
        if not raw:
            time.sleep(3)
            continue
        with POOL.open("a") as f:
            f.write(json.dumps({"uid": raw["uid"], "password": raw["password"],
                                "account_id": raw.get("account_id", "")}) + "\n")
        added += 1
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

    def has_warm_rank(self, dev):
        try:
            screen = dev.shot()
        except FlowError:
            return False
        return any(find(screen, t, conf=0.78)
                   for t in WARM_RANKS if _has_tpl(t))


def ensure_account(dev, provider, region, min_level, cfg, log=print):
    acct = provider.create(dev, region)
    if not provider.login(dev, acct):
        _record(acct, "login-failed")
        raise FlowError("login failed — guest login templates or account bad")

    acct.level = provider.validate(dev) or 0
    log(f"account {acct.account_id or acct.uid} level {acct.level}")

    tries = 0
    while acct.level < min_level and tries < cfg["accounts"]["warmup_max_matches"]:
        try:
            run_match(dev, cfg)
        except FlowError as e:
            log(f"warmup match error {e}")
        tries += 1
        acct.level = provider.validate(dev) or acct.level
        log(f"warmup {tries}/{cfg['accounts']['warmup_max_matches']} -> level {acct.level}")

    if acct.level < min_level:
        _record(acct, f"under-levelled:{acct.level}")
        raise FlowError(f"level {acct.level} < {min_level} after warmup")

    if cfg["accounts"].get("warm_rank") and not provider.has_warm_rank(dev):
        cap = cfg["accounts"]["rank_warm_max_matches"]
        for i in range(cap):
            try:
                run_match(dev, cfg)
            except FlowError:
                pass
            if provider.has_warm_rank(dev):
                log(f"rank warm reached after {i + 1} matches")
                break
        else:
            log("rank warm cap hit, continuing anyway")

    _record(acct, "ready")
    return acct
