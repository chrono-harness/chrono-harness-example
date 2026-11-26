import sys
startup_modules = tuple(sorted(sys.modules))
startup_origins = {
    name: getattr(getattr(sys.modules[name], "__spec__", None), "origin", None)
    for name in startup_modules
}
startup_path = [item.replace(sys.base_prefix, "<python>") for item in sys.path]
startup_path[0] = "<checkout>" if startup_path[0] == __file__.rsplit("/", 1)[0] else startup_path[0]
active = True
module_reads = []


def observe_loader(event, arguments):
    if active and event == "marshal.loads":
        module_reads.append(("bytecode", arguments[0]))
    if active and event == "compile" and isinstance(arguments[0], bytes):
        module_reads.append(("source", arguments[0]))


sys.addaudithook(observe_loader)
from pathlib import Path

# This qualification checkout records the source bytes actually compiled by
# Python's ordinary import of the example. The application has no dependencies.
module_path = str(Path(__file__).resolve().with_name("message.py"))
compiled_source = []


def observe_compile(event, arguments):
    if event == "compile":
        source, filename = arguments
        if filename == module_path:
            compiled_source.append(source)


sys.addaudithook(observe_compile)
from message import greeting

assert __debug__ and len(compiled_source) == 1
assert greeting.__code__.co_filename == module_path
business_text = Path("message.txt").read_text(encoding="utf-8")
assert greeting(business_text) == "hello"
assert greeting("  hello  ") == "hello"
assert greeting("\t\n") == ""
assert greeting("  hello world\n") == "hello world"

print("compiled message.py", compiled_source[0].hex())
print("decoded message.txt", business_text.encode("utf-8").hex())

# Finish observing before loading the reporting code.
active = False
business_modules = tuple(sorted(sys.modules))
import hashlib
import json

startup_files = {}
for name, origin in startup_origins.items():
    if origin in (None, "built-in", "frozen"):
        startup_files[name] = origin
    else:
        relative = Path(origin).relative_to(sys.base_prefix)
        startup_files[name] = [str(relative), hashlib.sha256(Path(origin).read_bytes()).hexdigest()]

observed = {
    "configured_cache": sys.pycache_prefix,
    "cache_present": Path(sys.pycache_prefix).exists(),
    "startup_origins": startup_files,
    "no_site": sys.flags.no_site,
    "startup_modules": startup_modules,
    "search_path": startup_path,
    "business_modules": business_modules,
    "loader_bytes": [(kind, len(raw), hashlib.sha256(raw).hexdigest()) for kind, raw in module_reads],
}
print("startup", json.dumps(observed, sort_keys=True, separators=(",", ":")))
