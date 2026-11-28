"""Adapt Python, shell and GitHub observations to the verified host decisions."""
import json
import os
import sys
from pathlib import Path


(WHITESPACE, SCHEMA, OPERATION, OID_LENGTHS, OID_DIGITS, STORAGE, RUST, LINKS,
 BUSINESS_CASES, CONTEXT_ORDER, CONTEXT_EXPECTED) = (
    Path(__file__).with_name("installer_storage.rs").read_text(encoding="utf-8")
    .split('macro_rules! host_projection {\n    () => { r#"', 1)[1].split('"#', 1)[0].splitlines()
)
TRIM_CHARS = "".join(chr(int(code, 16)) for code in WHITESPACE.split())
OID_LENGTHS = frozenset(map(int, OID_LENGTHS.split()))
OID_DIGITS = frozenset(OID_DIGITS)
BUSINESS_CASES = json.loads(BUSINESS_CASES)


def storage():
    """Reject the first contained path, or return the selected data directory."""
    overrides = [os.environ.get(name) for name in
                 ("CHRONO_EXAMPLE_INSTALL_ROOT", "MISE_DATA_DIR", "XDG_DATA_HOME")]
    explicit, mise, xdg = overrides
    decision = int(STORAGE[4 * bool(explicit) + 2 * bool(mise) + bool(xdg)])
    if decision == 0:
        data = os.environ["HOME"] + "/.local/share/mise"
    elif decision == 1:
        data = xdg + "/mise"
    else:
        data = (mise, explicit)[decision - 2]
    installs = os.environ.get("MISE_INSTALLS_DIR") or data + "/installs"
    store = os.environ.get("MISE_INSTALL_STORE_DIR") or installs
    downloads = os.environ.get("MISE_DOWNLOADS_DIR") or data + "/downloads"
    checkout = Path.cwd()
    for location in (data, installs, store, downloads):
        destination = Path(location).resolve()
        if destination == checkout or checkout in destination.parents:
            print(f"Choose a mise storage directory outside the checkout: {destination}",
                  file=sys.stderr)
            raise SystemExit(2)
    return data


def valid_oid(oid):
    if not isinstance(oid, str):
        raise TypeError("expected string or bytes-like object")
    return len(oid) in OID_LENGTHS and OID_DIGITS.issuperset(oid)


def full_context(raw):
    context = json.loads(raw)
    schema_error = "expected full check context schema 2"
    checks = {
        "S": (lambda: context["schema_version"] == int(SCHEMA), schema_error),
        "O": (lambda: context["operation"] == OPERATION, schema_error),
        "B": (lambda: valid_oid(context["base"]), "invalid fixed base"),
        "C": (lambda: valid_oid(context["candidate"]), "invalid fixed candidate"),
        "T": (lambda: context["base"] == context["dev_tip"],
              "the development tip differs from the base"),
    }
    for step in CONTEXT_ORDER:
        observes_valid, error = checks[step]
        if not observes_valid():
            raise ValueError(error)
    return context


if __name__ == "__main__":
    # The suffix preserves a trailing newline in a directory passed through sh.
    data = storage()
    print(RUST, LINKS)
    print(data, end=".")
