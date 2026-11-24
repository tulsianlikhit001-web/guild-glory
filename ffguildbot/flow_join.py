import time
from .device import FlowError
from .vision import tap_if, wait_for, exists, find


def join_guild(dev, guild_id, cfg):
    dev.ensure_foreground()
    if exists(dev, "badge_guild_member", conf=0.85):
        return "already"

    if not tap_if(dev, "btn_guild", timeout=25):
        raise FlowError("guild button not found — lobby template wrong or wrong screen")
    time.sleep(1.8)

    if not tap_if(dev, "btn_guild_search", timeout=15):
        raise FlowError("guild search not found")
    time.sleep(1.2)

    if not tap_if(dev, "field_guild_id", timeout=12):
        raise FlowError("guild id field not found")
    dev.text(str(guild_id))
    time.sleep(0.8)

    if not tap_if(dev, "btn_search_confirm", timeout=10):
        raise FlowError("search confirm not found")
    time.sleep(3.0)

    if exists(dev, "badge_guild_member", conf=0.85):
        return "already"

    if exists(dev, "popup_guild_full", conf=0.82):
        raise FlowError("guild full — free a slot")

    if tap_if(dev, "btn_guild_join", timeout=18):
        tap_if(dev, "btn_confirm", timeout=8)
        time.sleep(2.5)
        if exists(dev, "badge_guild_member", conf=0.85):
            return "joined"
        return "joined"

    if tap_if(dev, "btn_guild_apply", timeout=8, conf=0.85):
        time.sleep(1.5)
        return "pending"

    raise FlowError("no join or apply button — guild closed, level too low, or wrong guild id")


def wait_approved(dev, cfg, guild_id):
    end = time.time() + cfg["guild"]["approve_timeout_s"]
    while time.time() < end:
        if exists(dev, "badge_guild_member", conf=0.85):
            return "joined"
        dev.back()
        time.sleep(4)
        if exists(dev, "btn_guild", conf=0.85):
            tap_if(dev, "btn_guild", timeout=8)
            time.sleep(2)
            if exists(dev, "badge_guild_member", conf=0.85):
                return "joined"
        time.sleep(25)
    return "pending"


def leave_guild(dev):
    dev.ensure_foreground()
    if not tap_if(dev, "btn_guild", timeout=15):
        return False
    time.sleep(1.6)
    if not tap_if(dev, "btn_guild_members", timeout=12):
        return False
    time.sleep(1.2)
    tap_if(dev, "row_self_member", timeout=12)
    time.sleep(1.0)
    if tap_if(dev, "btn_leave_guild", timeout=10):
        tap_if(dev, "btn_confirm", timeout=8)
        time.sleep(1.8)
        return True
    return False
