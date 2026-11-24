#!/usr/bin/env bash
set -euo pipefail
S="$1"
adb -s "$S" shell svc power stayon true
adb -s "$S" shell settings put system screen_off_timeout 2147483647
adb -s "$S" shell settings put global window_animation_scale 0
adb -s "$S" shell settings put global transition_animation_scale 0
adb -s "$S" shell settings put global animator_duration_scale 0
adb -s "$S" shell settings put system accelerometer_rotation 0
adb -s "$S" shell settings put system user_rotation 0
adb -s "$S" shell cmd notification set_dnd on
adb -s "$S" shell settings put secure immersive_mode_confirmations confirmed
adb -s "$S" shell wm dismiss-keyguard
echo "provisioned $S"
