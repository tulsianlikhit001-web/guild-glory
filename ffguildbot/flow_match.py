import time, random
from .device import FlowError
from .vision import tap_if, wait_for, find


def run_match(dev, cfg):
    if not tap_if(dev, "btn_mode_br", timeout=20):
        raise FlowError("BR button not found")
    time.sleep(random.uniform(0.8, 1.6))
    if not tap_if(dev, "btn_start_match", timeout=20):
        raise FlowError("start button not found")
    if not wait_for(dev, "hud_land_button", timeout=120, conf=0.78):
        return "no_match"

    time.sleep(random.uniform(2.0, 6.0))
    tap_if(dev, "hud_land_button", timeout=25)

    deadline = time.time() + cfg["session"]["match_timeout_s"]
    while time.time() < deadline:
        screen = dev.shot()
        if find(screen, "btn_result_ok", conf=0.8):
            tap_if(dev, "btn_result_ok", timeout=6)
            return "finished"
        if find(screen, "hud_spectate", conf=0.8) or find(screen, "hud_dead", conf=0.8):
            tap_if(dev, "btn_result_ok", timeout=10)
            return "dead"
        _evade(dev, screen, cfg)
        time.sleep(random.uniform(1.1, 2.3))
    return "timeout"


def _evade(dev, screen, cfg):
    if find(screen, "warn_outside_zone", conf=0.72):
        dev.swipe_rel(0.82, 0.50, 0.20, 0.50, 380)
        dev.tap_rel(0.93, 0.78)
        return
    if find(screen, "warn_enemy_near", conf=cfg["vision"]["enemy_conf"]):
        dev.swipe_rel(0.55, 0.50, 0.30, 0.52, 220)
        dev.tap_rel(0.90, 0.80)
        return
    if random.random() < 0.35:
        dev.tap_rel(0.93, 0.78)
    if random.random() < 0.12:
        dev.swipe_rel(0.60, 0.50, 0.42, 0.50, 240)
