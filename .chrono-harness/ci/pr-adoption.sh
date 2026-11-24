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
result=$("$release" pr-status --pr "$number" --head-sha "$expected") || {
  rc=$?
  jq '{pr, pr_state, expected_head, observed_head, merge_commit, outcome, error, checks}' <<< "$result" >&2
  exit "$rc"
}
jq -e --arg expected "$expected" --arg landed "$landed" --argjson number "$number" \
  '.schema == "chrono-pr-result/v3" and .pr == $number and .pr_state == "MERGED"
   and .observed_head == $expected and .merge_commit == $landed and .command_exit_code == 0' <<< "$result"

# Exercise the installed client on a disposable checkout-local reminder database.
fixture=$(mktemp -d)
cleanup_fixture() {
  if [[ -f "$database" ]]; then unlink "$database"; fi
  rmdir "$fixture/.chrono-harness" "$fixture"
}
mkdir -p "$fixture/.chrono-harness"
database="$fixture/.chrono-harness/pr-reminders.sqlite3"
trap cleanup_fixture EXIT
sqlite3 "$database" <<'SQL'
CREATE TABLE reminder(
  repository TEXT NOT NULL, number INTEGER NOT NULL, head TEXT NOT NULL,
  expires INTEGER NOT NULL, PRIMARY KEY(repository,number)
) WITHOUT ROWID;
INSERT INTO reminder VALUES ('example/host', 1, 'expired', unixepoch() - 1);
INSERT INTO reminder VALUES ('example/host', 2, 'boundary', unixepoch());
INSERT INTO reminder VALUES ('example/host', 3, 'live', unixepoch() + 86400);
SQL
"$release" pr-reminders --host-root "$fixture" | jq -e '[.pull_requests[].pr] == [3]'
test "$(sqlite3 "$database" 'SELECT group_concat(number) FROM reminder')" = 3
