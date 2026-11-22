from pathlib import Path
from message import greeting

assert greeting(Path("message.txt").read_text()) == "hello"
assert greeting("  hello  ") == "hello"
assert greeting("\t\n") == ""
assert greeting("  hello world\n") == "hello world"
