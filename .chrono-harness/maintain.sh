#!/bin/sh
# Run both local owners even if one reports a failure.
status=0
reminders=$(.chrono-harness/bin/chrono-pr pr-reminders) || {
    status=$?
    printf '%s\n' "$reminders" >&2
}
.chrono-harness/bin/chrono-worktree maintain || status=$?
exit "$status"
