#!/usr/bin/env python3
"""Tests for skills/smart-research/scripts/check-research.py. Standard library only.

  python3 -I evals/test-check-research.py

Exit 0: all pass. Exit 1: at least one failure.
"""
import subprocess
import sys
import tempfile
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent.parent / "skills" / "smart-research" / "scripts" / "check-research.py"
FAILS = []

GOOD = """# Analysis: Does the retry helper of libfoo back off?
Status: FINAL · Run reference: libfoo-retry + 2026-11-25
Area: research · Module: libfoo

## Question
Does libfoo retry with exponential back-off by default?

## Findings
- The default policy waits 100 ms and doubles each time, up to 5 attempts. [S1]
- A blog post says the cap is 10 s; the official page does not state a cap. [S2] UNVERIFIED
- Our own wrapper sets the attempt count to 3. (code: src/net/client.py)
  A continuation line may be indented and needs no citation of its own.

## Hypotheses & evidence
- H1 the default is linear -> ruled out by [S1].

## Answer / root cause
Exponential back-off by default. Confidence: High (the official docs state it).

## Recommendation
Set the cap explicitly.

## Sources
| ID | URL | Publisher | Kind | Retrieved |
|---|---|---|---|---|
| S1 | https://docs.libfoo.example/retry | libfoo project | primary | 2026-11-25 |
| S2 | https://blog.example/libfoo-retry | a blog | secondary | 2026-11-25 |
"""


def run(text, *extra, name="analysis.md"):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / name
        p.write_text(text)
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(p), *extra], capture_output=True, text=True)
        return r.returncode, r.stdout + r.stderr


def check(name, cond, detail=""):
    if not cond:
        FAILS.append(f"FAIL {name} {detail}")


def fails(name, text, needle):
    rc, out = run(text)
    check(name, rc == 1 and needle.lower() in out.lower(), f"rc={rc} {out}")


def test_good():
    rc, out = run(GOOD)
    check("a good file prints OK", rc == 0 and out.startswith("OK"), out)
    rc, out = run("﻿" + GOOD)
    check("a byte order mark is read through", rc == 0, out)
    rc, out = run(GOOD, name="notes.txt")
    check("a non-Markdown file is exit 2", rc == 2, out)


def test_headings_and_header():
    fails("missing Sources heading", GOOD.replace("## Sources", "## Links"), "Sources")
    fails("missing Recommendation heading", GOOD.replace("## Recommendation\nSet the cap explicitly.\n\n", ""), "Recommendation")
    fails("missing title", GOOD.replace("# Analysis:", "# Note:"), "title")
    fails("status not FINAL", GOOD.replace("Status: FINAL", "Status: DRAFT"), "Status")
    fails("missing Confidence line", GOOD.replace("Confidence: High", "Sure"), "Confidence")
    fails("bad Confidence value", GOOD.replace("Confidence: High", "Confidence: Certain"), "Confidence")


def test_findings():
    fails("a finding without a source", GOOD.replace("up to 5 attempts. [S1]", "up to 5 attempts."), "no source")
    fails("an uncited prose line under Findings", GOOD.replace("## Findings\n", "## Findings\nIt is widely known to work.\n"), "no source")
    fails("a cited id missing from Sources", GOOD.replace("ruled out by [S1]", "ruled out by [S3]"), "S3")
    ok = GOOD.replace("- Our own wrapper", "```\nplain code, no citation needed\n```\n- Our own wrapper")
    rc, out = run(ok)
    check("text inside a code fence is not a finding", rc == 0, out)


def test_sources():
    fails("a source never cited", GOOD.replace(" [S2] UNVERIFIED", " UNVERIFIED"), "S2")
    fails("an http URL", GOOD.replace("https://docs.libfoo", "http://docs.libfoo"), "https")
    fails("no Retrieved date", GOOD.replace("| primary | 2026-11-25 |", "| primary | |"), "Retrieved")
    fails("a bad Retrieved date", GOOD.replace("| primary | 2026-11-25 |", "| primary | 25-11-2026 |"), "Retrieved")
    fails("a future Retrieved date", GOOD.replace("| primary | 2026-11-25 |", "| primary | 2999-01-01 |"), "future")
    fails("an unknown kind", GOOD.replace("| primary |", "| official |"), "kind")
    fails("a duplicate source id", GOOD.replace("| S2 |", "| S1 |"), "duplicate")
    for q in ("token", "key", "secret", "password", "sig"):
        fails(f"a {q}= credential in the URL", GOOD.replace("/retry |", f"/retry?x=1&{q}=abc |"), "credential")
    fails("a token in the URL fragment", GOOD.replace("/retry |", "/retry#access_token=abc |"), "credential")
    fails("a user:password@ URL", GOOD.replace("https://docs.libfoo", "https://me:pw@docs.libfoo"), "credential")
    rc, out = run(GOOD.replace("/retry |", "/retry?page=2&lang=en |"))
    check("an ordinary query string is allowed", rc == 0, out)


def swap(old, new):
    return GOOD.replace(old, new)


def test_review_fixes():
    url = "https://docs.libfoo.example/retry"
    # R1 credential keys beyond the first five, written in other spellings
    for key in ("client_secret", "auth_token", "X-Amz-Signature", "api-key", "private_key", "pwd", "jwt", "sessionid"):
        fails(f"R1 {key}= in the URL", swap(url + " |", f"{url}?{key}=abc |"), "credential")
    rc, out = run(swap(url + " |", f"{url}?author=bob&monkey=1&page=2 |"))
    check("R1 author= and monkey= are not credentials", rc == 0, out)
    # R2 bypasses of the query and fragment parsing
    for tail in ("?a=1;token=abc", "#/cb?token=abc", "?%2574oken=abc", "/Zk3Jq8Xw2Lm9Vb4Nc7Rt1Yh5Pd6Sa0Ge"):
        fails(f"R2 {tail}", swap(url + " |", url + tail + " |"), "credential")
    # R3 more than five cells, or a link in another cell
    fails("R3 a sixth cell", swap("| 2026-11-25 |\n| S2", "| 2026-11-25 | extra |\n| S2"), "columns")
    fails("R3 a link in the Publisher cell", swap("| libfoo project |", "| http://evil.example/x |"), "link")
    # R4 a secret-bearing link anywhere in the prose
    fails("R4 a token link in a finding", swap("up to 5 attempts. [S1]", "up to 5 attempts, see https://x.example/?token=abc [S1]"), "credential")
    rc, out = run(swap("up to 5 attempts. [S1]", "up to 5 attempts, see https://x.example/page [S1]"))
    check("R4 an ordinary link in prose is allowed", rc == 0, out)
    # R5 the unfilled template line
    fails("R5 Confidence template", swap("Confidence: High", "Confidence: High | Medium | Low"), "Confidence")
    # R6 the host
    for host in ("...", "localhost", "10.0.0.1", "intranet", "127.0.0.1"):
        fails(f"R6 host {host}", swap("https://docs.libfoo.example/retry", f"https://{host}/retry"), "host")
    # R7 unpadded date
    fails("R7 an unpadded date", swap("| primary | 2026-11-25 |", "| primary | 2026-1-5 |"), "Retrieved")
    # R8 the citation must end the line
    fails("R8 a hidden citation", swap("up to 5 attempts. [S1]", "[S1] hidden; the real claim has no source"), "no source")
    rc, out = run(swap("up to 5 attempts. [S1]", "up to 5 attempts. [S1]."))
    check("R8 a citation followed by a full stop passes", rc == 0, out)
    # R9 invalid UTF-8 is an unreadable file; a Unicode digit is not an id
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bad.md"
        p.write_bytes(GOOD.encode() + b"\xff\xfe")
        r = subprocess.run([sys.executable, "-I", str(SCRIPT), str(p)], capture_output=True, text=True)
        check("R9 invalid UTF-8 is exit 2", r.returncode == 2, r.stdout + r.stderr)
    fails("R9 an Arabic-digit id is not a citation", swap("attempts. [S1]", "attempts. [S\u0661]"), "no source")
    # R10 a row of empty cells
    fails("R10 an empty row", GOOD + "| | | | | |\n", "Retrieved")
    # R13 a citation inside a table of another section counts
    table = "## Hypotheses & evidence\n| H | verdict |\n|---|---|\n| H1 | ruled out by [S2] |\n"
    rc, out = run(swap("## Hypotheses & evidence\n- H1 the default is linear -> ruled out by [S1].\n", table).replace(" [S2] UNVERIFIED", " UNVERIFIED"))
    check("R13 a citation in a Hypotheses table counts", rc == 0, out)
    # R11 and R12 are instruction text: the rules are in SKILL.md
    skill = (SCRIPT.parent.parent / "SKILL.md").read_text()
    check("R11 SKILL.md limits fetched URLs", "Fetch only URLs" in skill and "different host" in skill)
    check("R12 SKILL.md says --no-save still checks a scratch draft", "`--no-save` still checks" in skill)


def test_qa_report_fixes():
    # QA-1: a credential link hidden in a code fence, or behind an unclosed fence, is still caught
    fenced = GOOD.replace("## Recommendation", "```\ncurl https://api.example.com/v1?token=abc123\n```\n## Recommendation")
    fails("QA-1 a token link inside a fenced block", fenced, "credential")
    unclosed = GOOD + "\n```\n- uncited claim after an unclosed fence\n- see https://x.example/?token=abc123\n"
    rc, out = run(unclosed)
    check("QA-1 an unclosed fence fails", rc == 1 and "fence" in out.lower(), out)
    check("QA-1 the link behind the unclosed fence is reported too", "credential" in out.lower(), out)
    harmless = GOOD.replace("## Recommendation", "```\ncurl https://api.example.com/v1/items\n```\n## Recommendation")
    rc, out = run(harmless)
    check("QA-1 a fenced block with an ordinary link passes", rc == 0, out)
    mixed = GOOD.replace("## Recommendation", "~~~\n```\n~~~\n## Recommendation")
    rc, out = run(mixed)
    check("QA-1 a ``` line inside a ~~~ block does not toggle the fence", rc == 0, out)
    # QA-2: a citation followed by closing punctuation is still a citation
    for tail in ("([S1])", "[S1]:", "**the default is 5 [S1]**", "_the default is 5 [S1]_", "[S1];", "(see [S1])"):
        rc, out = run(swap("up to 5 attempts. [S1]", f"up to 5 attempts {tail}") if tail.startswith(("(", "[")) else
                      swap("- The default policy waits 100 ms and doubles each time, up to 5 attempts. [S1]", f"- {tail}"))
        check(f"QA-2 {tail!r} counts as cited", rc == 0, out)
    fails("QA-2 a citation followed by more words still fails", swap("up to 5 attempts. [S1]", "up to 5 attempts. [S1] and then an uncited claim"), "no source")


def main():
    test_good()
    test_headings_and_header()
    test_findings()
    test_sources()
    test_review_fixes()
    test_qa_report_fixes()
    if FAILS:
        print("\n".join(FAILS))
        return 1
    print("OK all check-research tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
