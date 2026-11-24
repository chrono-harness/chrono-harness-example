#!/bin/sh
set -eu
/bin/sh .chrono-harness/ci/install.sh
export CHRONO_CHECK_SOURCE=ci
exec python3 -B .chrono-harness/ci/full-round.py produce
