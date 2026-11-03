#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
python3 sched.py --algo all set1.txt
python3 sched.py --algo rr --quantum 3 set1.txt
python3 experiment.py
