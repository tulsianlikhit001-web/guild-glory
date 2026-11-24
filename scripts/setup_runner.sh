#!/usr/bin/env bash
set -euo pipefail
sudo apt-get update
sudo apt-get install -y android-tools-adb tesseract-ocr tesseract-ocr-eng \
  python3-venv python3-pip
python3 -m venv .venv
. .venv/bin/activate
pip install -r requirements-runner.txt
python patch_ffapi.py
mkdir -p ffguildbot/templates state
echo "done — activate venv, fill runner.env, run: python runner.py"
