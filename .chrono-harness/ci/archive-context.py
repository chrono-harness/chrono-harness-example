"""Preserve the submitted worktree context and report its artifact identity."""
import hashlib
import os
from pathlib import Path

from host_decisions import full_context


raw = os.environ["FULL_CONTEXT"].encode("utf-8")
context = full_context(raw)
Path("context.json").write_bytes(raw)
with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as output:
    print("name=full-round-" + context["candidate"] + "-" + context["base"], file=output)
print("Context SHA-256", hashlib.sha256(raw).hexdigest())
