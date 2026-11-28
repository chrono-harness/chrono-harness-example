//! Host decisions used by the standalone Python example and the CI bootstrap.
//! Python supplies JSON, Unicode strip and resolved paths. The shell supplies
//! environment presence, uname and file observations. Neither adapter needs
//! the proof toolchain to start.
use vstd::prelude::*;

verus! {

pub fn policy_inputs() -> [&'static str; 8] {
    [
        include_str!("decision-values.txt"),
        include_str!("install.sh"),
        include_str!("host_decisions.py"),
        include_str!("check-install-location.py"),
        include_str!("archive-context.py"),
        include_str!("../../.github/workflows/full-round.yml"),
        include_str!("../../message.py"),
        include_str!("../../check.py"),
    ]
}

spec fn storage_choice(explicit: bool, mise: bool, xdg: bool) -> char {
    if explicit { '3' } else if mise { '2' } else if xdg { '1' } else { '0' }
}

spec fn rust_choice(hosted: bool, harness: bool) -> char {
    if !hosted || harness { '1' } else { '0' }
}

spec fn link_choice(symlink: bool, same: bool, occupied: bool) -> char {
    if symlink { if same { 'k' } else { 'r' } }
    else if occupied { 'f' }
    else { 'c' }
}

spec fn bit(value: bool) -> int { if value { 1 } else { 0 } }

proof fn all_storage_observations(a: bool, b: bool, c: bool) {
    reveal_projection();
    reveal_strlit("01223333");
    assert(projection().subrange(185, 193)[4 * bit(a) + 2 * bit(b) + bit(c)] == storage_choice(a, b, c));
}

proof fn all_rust_observations(a: bool, b: bool) {
    reveal_projection();
    reveal_strlit("1101");
    assert(projection().subrange(194, 198)[2 * bit(a) + bit(b)] == rust_choice(a, b));
}

proof fn all_link_observations(a: bool, b: bool, c: bool) {
    reveal_projection();
    reveal_strlit("cfcfrrkk");
    assert(projection().subrange(199, 207)[4 * bit(a) + 2 * bit(b) + bit(c)] == link_choice(a, b, c));
}

spec fn oid_digit(c: char) -> bool {
    '0' <= c <= '9' || 'a' <= c <= 'f'
}

proof fn all_oid_characters(c: char) {
    reveal_strlit("0123456789abcdef");
    reveal_projection();
    let digits = projection().subrange(168, 184);
    assert forall|i: int| 0 <= i < digits.len() implies oid_digit(#[trigger] digits[i]) by {};
    if oid_digit(c) {
        let index = if c <= '9' { c as int - '0' as int } else { c as int - 'a' as int + 10 };
        assert(digits[index] == c);
        assert(digits.contains(c));
    } else if digits.contains(c) {
        let index = choose|i: int| 0 <= i < digits.len() && digits[i] == c;
        assert(oid_digit(digits[index]));
    }
    assert(digits.contains(c) == oid_digit(c));
}

spec fn is_space(c: char) -> bool {
    0x09 <= c as int <= 0x0d || 0x1c <= c as int <= 0x20 ||
    c as int == 0x85 || c as int == 0xa0 || c as int == 0x1680 ||
    0x2000 <= c as int <= 0x200a || c as int == 0x2028 || c as int == 0x2029 ||
    c as int == 0x202f || c as int == 0x205f || c as int == 0x3000
}

spec fn strips(input: Seq<char>, start: int, end: int, expected: Seq<char>) -> bool {
    &&& 0 <= start <= end <= input.len()
    &&& input.subrange(start, end) == expected
    &&& forall|i: int| 0 <= i < start || end <= i < input.len() ==> is_space(#[trigger] input[i])
    &&& expected.len() > 0 ==> !is_space(expected[0]) && !is_space(expected[expected.len() - 1])
}

proof fn business_cases() {
    reveal_strlit("  hello  ");
    reveal_strlit("hello");
    assert("  hello  "@.subrange(2, 7) =~= "hello"@);
    assert(strips("  hello  "@, 2, 7, "hello"@));
    reveal_strlit("\t\n");
    reveal_strlit("");
    assert("\t\n"@.subrange(2, 2) =~= ""@);
    assert(strips("\t\n"@, 2, 2, ""@));
    reveal_strlit("  hello world\n");
    reveal_strlit("hello world");
    assert("  hello world\n"@.subrange(2, 13) =~= "hello world"@);
    assert(strips("  hello world\n"@, 2, 13, "hello world"@));
    reveal_strlit("\u{1c}\u{200a}word\u{3000}");
    reveal_strlit("word");
    assert("\u{1c}\u{200a}word\u{3000}"@.subrange(2, 6) =~= "word"@);
    assert(strips("\u{1c}\u{200a}word\u{3000}"@, 2, 6, "word"@));
    reveal_strlit("\u{200b}word\u{200b}");
    assert("\u{200b}word\u{200b}"@.subrange(0, 6) =~= "\u{200b}word\u{200b}"@);
    assert(strips("\u{200b}word\u{200b}"@, 0, 6, "\u{200b}word\u{200b}"@));
}

// Boundaries of the lines consumed by the adapter. The proof checks their
// separators as well as the complete contents of each interpreted field.
spec fn projection() -> Seq<char> {
    include_str!("decision-values.txt")@
}

proof fn reveal_projection()
    ensures
        projection().len() == 352,
        projection().subrange(0, 144) == "0009 000A 000B 000C 000D 001C 001D 001E 001F 0020 0085 00A0 1680 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 200A 2028 2029 202F 205F 3000"@,
        projection()[145] == '2',
        projection().subrange(147, 161) == "validate.delta"@,
        projection().subrange(162, 167) == "40 64"@,
        projection().subrange(168, 184) == "0123456789abcdef"@,
        projection().subrange(185, 193) == "01223333"@,
        projection().subrange(194, 198) == "1101"@,
        projection().subrange(199, 207) == "cfcfrrkk"@,
        projection().subrange(208, 351) == r#"[["  hello  ","hello"],["\t\n",""],["  hello world\n","hello world"],["\u001c\u200aword\u3000","word"],["\u200bword\u200b","\u200bword\u200b"]]"#@,
        forall|index: int|
            index == 144 || index == 146 || index == 161 || index == 167 ||
            index == 184 || index == 193 || index == 198 || index == 207 || index == 351
            ==> #[trigger] projection()[index] == '\n',
{
    reveal_strlit(include_str!("decision-values.txt"));
    reveal_strlit("0009 000A 000B 000C 000D 001C 001D 001E 001F 0020 0085 00A0 1680 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 200A 2028 2029 202F 205F 3000");
    reveal_strlit("validate.delta");
    reveal_strlit("40 64");
    reveal_strlit("0123456789abcdef");
    reveal_strlit("01223333");
    reveal_strlit("1101");
    reveal_strlit("cfcfrrkk");
    reveal_strlit(r#"[["  hello  ","hello"],["\t\n",""],["  hello world\n","hello world"],["\u001c\u200aword\u3000","word"],["\u200bword\u200b","\u200bword\u200b"]]"#);
    assert(projection().subrange(0, 144) =~= "0009 000A 000B 000C 000D 001C 001D 001E 001F 0020 0085 00A0 1680 2000 2001 2002 2003 2004 2005 2006 2007 2008 2009 200A 2028 2029 202F 205F 3000"@);
    assert(projection().subrange(147, 161) =~= "validate.delta"@);
    assert(projection().subrange(162, 167) =~= "40 64"@);
    assert(projection().subrange(168, 184) =~= "0123456789abcdef"@);
    assert(projection().subrange(185, 193) =~= "01223333"@);
    assert(projection().subrange(194, 198) =~= "1101"@);
    assert(projection().subrange(199, 207) =~= "cfcfrrkk"@);
    assert(projection().subrange(208, 351) =~= r#"[["  hello  ","hello"],["\t\n",""],["  hello world\n","hello world"],["\u001c\u200aword\u3000","word"],["\u200bword\u200b","\u200bword\u200b"]]"#@);
}

}
