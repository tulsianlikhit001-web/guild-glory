#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."

sudo apt-get update
sudo apt-get install -y adb tesseract-ocr python3-venv

python3 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r requirements-runner.txt

adb start-server
adb devices

echo "--- template check ---"
python scripts/check_templates.py || echo "capture the missing ones before launching jobs"

echo
echo "next: cp runner.env.example runner.env, fill it, then: python runner.py"
