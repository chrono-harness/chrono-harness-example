//! The bootstrap table is executed by install.sh before the first tool download.
//! check-install-location.py checks the shell selects these rows from real path observations.
use vstd::prelude::*;

verus! {
proof fn deployed_storage_rows_match_the_install_policy() {
    let script = include_str!("install.sh");
    let rows = "        storage-0) choice=accept ;;\n        storage-1) choice=reject ;;\n";
    reveal_strlit(include_str!("install.sh"));
    reveal_strlit("        storage-0) choice=accept ;;\n        storage-1) choice=reject ;;\n");
    // Witness for the two consecutive arms in the generated dispatch function.
    assert(script@.subrange(523, 523 + rows@.len() as int) =~= rows@);
}
}
