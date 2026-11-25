#!/bin/sh
# Run each local owner even if an earlier maintenance operation fails.
status=0
reminders=$(.chrono-harness/bin/chrono-pr pr-reminders) || {
    status=$?
    printf '%s\n' "$reminders" >&2
}
.chrono-harness/bin/chrono-worktree maintain || status=$?
.chrono-harness/bin/chrono-distribution maintain --host-root . --keep-seconds 86400 || status=$?
exit "$status"
