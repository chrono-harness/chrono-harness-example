#!/usr/bin/env bash
set -euo pipefail
release=$(mise which chrono-pr)
"$release" pr-reminders | jq -e '.schema == "chrono-pr-reminders/v1" and (.pull_requests | type == "array")'
# Inspect a genuinely landed PR, also when an independent push triggered this run.
merged=$(gh api --method GET "repos/$GITHUB_REPOSITORY/pulls" \
  -f state=closed -f base=dev -f sort=updated -f direction=desc -F per_page=100 \
  --jq '[.[] | select(.merged_at != null)][0] | [.number,.head.sha,.merge_commit_sha] | @tsv')
read -r number expected landed <<< "$merged"
test -n "$number" && test -n "$expected" && test -n "$landed"
"$release" pr-status --pr "$number" --head-sha "$expected" |
  jq -e --arg expected "$expected" --arg landed "$landed" --argjson number "$number" \
  '.schema == "chrono-pr-result/v3" and .pr == $number and .pr_state == "MERGED"
   and .observed_head == $expected and .merge_commit == $landed and .command_exit_code == 0'
