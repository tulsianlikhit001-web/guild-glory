#!/usr/bin/env python3
"""Report templates the code expects vs what exists. Exit 1 if any missing."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TPL = ROOT / "ffguildbot" / "templates"

REQUIRED = [
    "btn_login_guest", "btn_guest_recover", "field_guest_uid", "btn_guest_next",
    "field_guest_pw", "btn_guest_confirm", "hud_lobby_ready",
    "badge_guild_member", "btn_guild", "btn_guild_search", "field_guild_id",
    "btn_search_confirm", "btn_guild_join", "btn_guild_apply", "btn_confirm",
    "popup_guild_full", "btn_guild_members", "row_self_member", "btn_leave_guild",
    "btn_mode_br", "btn_start_match", "hud_land_button", "btn_result_ok",
    "hud_spectate", "hud_dead", "warn_outside_zone", "warn_enemy_near",
]

present = {p.stem for p in TPL.glob("*.png")} if TPL.exists() else set()
missing = [n for n in REQUIRED if n not in present]
extra = sorted(present - set(REQUIRED))

for n in missing:
    print(f"MISSING  {n}")
for n in extra:
    print(f"extra    {n}")

print(f"\n{len(REQUIRED) - len(missing)}/{len(REQUIRED)} required templates present")
sys.exit(1 if missing else 0)
