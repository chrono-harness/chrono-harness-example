#!/bin/sh
set -eu
python3 -B .chrono-harness/ci/check-install-location.py
exec .chrono-harness/bin/chrono-ci verify --host-root . --config .chrono-harness/ci/units.json
