#!/usr/bin/env python3
"""Mechanical check for a smart-research analysis file. Standard library only. Read-only.

  check-research.py ANALYSIS.md

Proves what a script can prove:
  - the title line `# Analysis: <question>` and `Status: FINAL`
  - the required headings: Question, Findings, Answer / root cause, Recommendation, Sources
  - a `Confidence: High|Medium|Low` line
  - every unindented line under Findings ENDS in a source id `[S<n>]`, or `UNVERIFIED`, or names the user's
    own code as `(code: <path>)` (a full stop after it is fine)
  - every cited `[S<n>]` exists in the Sources table, and every source is cited at least once
  - each Sources row `| ID | URL | Publisher | Kind | Retrieved |` has exactly 5 cells, a unique id, an https URL
    on a public DNS name or address with no credential (no user:password@, no token, key, secret, password,
    sig, jwt, session or similar key in the query or fragment, however spelled or encoded, and no secret-looking
    path segment), a Kind of primary or secondary, and a Retrieved date YYYY-MM-DD that is not in the future
  - no link anywhere in the file, code fences included, carries a credential-like key; a code fence that is
    never closed fails (it would hide everything after it)

It does not judge whether a source really supports its claim: re-reading the primary page is the skill's job.

Exit 0: no problems. Exit 1: at least one FAIL line. Exit 2: bad usage or unreadable file.
"""
import argparse
import ipaddress
import re
import sys
from datetime import date, datetime
from pathlib import Path
from urllib.parse import unquote, urlsplit

REQUIRED = ["Question", "Findings", "Answer / root cause", "Recommendation", "Sources"]
# A key counts as a credential when, lowercased with `-` and `_` removed, it is one of CRED_EXACT or holds one of CRED_PART.
CRED_EXACT = {"key", "sig", "pwd", "jwt", "auth", "authorization"}
CRED_PART = ("token", "secret", "passw", "apikey", "privatekey", "accesskey", "secretkey", "clientkey",
             "signature", "credential", "bearer", "session")
LINK = re.compile(r"[A-Za-z][A-Za-z0-9+.-]*://[^\s)>\]\"'<]+")
DNS = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?(\.[a-z0-9]([a-z0-9-]*[a-z0-9])?)+$")
ENDS_WITH_SOURCE = re.compile(r"(\[S[0-9]+\]|UNVERIFIED|\(code: \S+\))[ \t.:;,)\]*_\"']*$")
FENCE = re.compile(r"^\s*(`{3,}|~{3,})")
CITE = re.compile(r"\[S([0-9]+)\]")
FAILS = []


def fail(check, msg):
    FAILS.append(f"FAIL {check}: {msg}")


def strip_fences(lines):
    """Lines outside code fences, and whether every fence was closed.

    A fence opens with 3 or more of one character (` or ~) and closes only with the same character,
    at least as many times, and nothing else on the line."""
    out, marker = [], None
    for ln in lines:
        m = FENCE.match(ln)
        if marker is None:
            if m:
                marker = m.group(1)
                continue
            out.append(ln)
        elif m and m.group(1)[0] == marker[0] and len(m.group(1)) >= len(marker) and not ln.strip().strip(marker[0]):
            marker = None
    return out, marker is None


def section(lines, name):
    """Lines under `## name` up to the next `## ` heading."""
    body, inside = [], False
    for ln in lines:
        if re.match(r"^## ", ln):
            inside = ln[3:].strip() == name
            continue
        if inside:
            body.append(ln)
    return body


def outside_sources(lines):
    """Every line that is not under the `## Sources` heading."""
    out, inside = [], False
    for ln in lines:
        if re.match(r"^## ", ln):
            inside = ln[3:].strip() == "Sources"
        if not inside:
            out.append(ln)
    return out


def credential_hits(url):
    """Names of credential-like keys, and a note for a secret-looking path segment, anywhere in the URL."""
    text = url
    for _ in range(5):
        decoded = unquote(text)
        if decoded == text:
            break
        text = decoded
    hits = set()
    for piece in re.split(r"[&;?#/]", text):
        if "=" not in piece:
            continue
        key = piece.split("=", 1)[0].lower().replace("-", "").replace("_", "")
        if key in CRED_EXACT or any(part in key for part in CRED_PART):
            hits.add(piece.split("=", 1)[0].lower())
    path = urlsplit(text).path
    for seg in path.split("/"):
        if (len(seg) >= 24 and re.fullmatch(r"[A-Za-z0-9_-]+", seg) and re.search(r"[0-9]", seg)
                and re.search(r"[a-z]", seg) and re.search(r"[A-Z]", seg)):
            hits.add("a path segment that looks like a secret")
    return sorted(hits)


def bad_host(host):
    if not host:
        return True
    host = host.lower()
    try:
        ip = ipaddress.ip_address(host)
        return not ip.is_global
    except ValueError:
        pass
    return not DNS.match(host) or host == "localhost" or host.endswith((".local", ".internal", ".localhost"))


def check_source(row, seen):
    cells = [c.strip() for c in row.strip().strip("|").split("|")]
    if len(cells) != 5:
        fail("sources", f"row has {len(cells)} columns, expected ID | URL | Publisher | Kind | Retrieved: {row.strip()[:60]}")
        return None
    sid, url, publisher, kind, retrieved = cells
    if sid in seen:
        fail("sources", f"duplicate source id {sid}")
    seen.add(sid)
    for name, cell in (("ID", sid), ("Publisher", publisher), ("Kind", kind), ("Retrieved", retrieved)):
        if LINK.search(cell):
            fail("sources", f"{sid or '(no id)'} a link in the {name} cell; links belong in the URL cell only")
    parts = urlsplit(url)
    if parts.scheme != "https" or not parts.netloc:
        fail("sources", f"{sid} URL must be https")
    elif "@" in parts.netloc:
        fail("sources", f"{sid} URL holds a credential (user:password@)")
    else:
        if bad_host(parts.hostname):
            fail("sources", f"{sid} URL host is not a public DNS name or address: {parts.hostname}")
        bad = credential_hits(url)
        if bad:
            fail("sources", f"{sid} URL holds a credential-like value ({', '.join(bad)})")
    if kind.lower() not in ("primary", "secondary"):
        fail("sources", f"{sid} kind must be primary or secondary, got {kind!r}")
    if not re.fullmatch(r"[0-9]{4}-[0-9]{2}-[0-9]{2}", retrieved):
        fail("sources", f"{sid} needs a Retrieved date YYYY-MM-DD, got {retrieved!r}")
    else:
        try:
            if datetime.strptime(retrieved, "%Y-%m-%d").date() > date.today():
                fail("sources", f"{sid} Retrieved date {retrieved} is in the future")
        except ValueError:
            fail("sources", f"{sid} Retrieved date {retrieved} is not a real date")
    return sid


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("analysis")
    path = Path(ap.parse_args().analysis)
    if not path.is_file() or path.suffix.lower() != ".md":
        print(f"ERROR [check-research.py]: {path} is not a Markdown (.md) file", file=sys.stderr)
        print("NEXT: pass the path of the saved analysis file, then run again.", file=sys.stderr)
        sys.exit(2)
    try:
        text = path.read_text(encoding="utf-8-sig")
    except (UnicodeDecodeError, OSError) as err:
        print(f"ERROR [check-research.py]: {path} is not readable as UTF-8 ({type(err).__name__})", file=sys.stderr)
        print("NEXT: save the file as UTF-8, then run again.", file=sys.stderr)
        sys.exit(2)
    raw = text.splitlines()
    lines, balanced = strip_fences(raw)
    if not balanced:
        fail("fences", "a code fence is opened but never closed; everything after it would escape the checks")
    if not any(re.match(r"^# Analysis:\s*\S", ln) for ln in lines):
        fail("header", "no `# Analysis: <question>` title line")
    status = next((re.match(r"Status:\s*(\S+)", ln) for ln in lines[:8] if ln.startswith("Status:")), None)
    if not status or status.group(1) != "FINAL":
        fail("header", "`Status: FINAL` is required in the header")
    headings = [ln[3:].strip() for ln in lines if re.match(r"^## ", ln)]
    for name in REQUIRED:
        if name not in headings:
            fail("headings", f"missing `## {name}`")
    if not any(re.search(r"\bConfidence:\s*(High|Medium|Low)\b(?!\s*\|)", ln) for ln in lines):
        fail("confidence", "no `Confidence: High|Medium|Low` line")

    for ln in section(lines, "Findings"):
        if not ln.strip() or ln.startswith((" ", "\t", "#")):
            continue
        if not ENDS_WITH_SOURCE.search(ln):
            fail("findings", f"no source on: {ln.strip()[:70]}")

    seen, rows = set(), []
    for ln in section(lines, "Sources"):
        separator = re.match(r"^\s*\|[\s:|-]+\|\s*$", ln) and "-" in ln
        if ln.strip().startswith("|") and not separator and not re.match(r"^\s*\|\s*ID\s*\|", ln, re.I):
            sid = check_source(ln, seen)
            if sid:
                rows.append(sid)
    outside = outside_sources(lines)
    cited = {f"S{n}" for ln in outside for n in CITE.findall(ln)}
    # The credential scan reads the raw text, code fences included: a secret in a code block is still a secret.
    for no, ln in enumerate(raw, 1):
        for link in LINK.findall(ln):
            bad = credential_hits(link)
            if bad:
                fail("links", f"line {no}: a link holds a credential-like value ({', '.join(bad)})")
    for sid in sorted(cited - seen, key=lambda s: int(s[1:])):
        fail("citations", f"[{sid}] is cited but not in Sources")
    for sid in sorted(seen - cited, key=lambda s: (len(s), s)):
        fail("citations", f"{sid} is in Sources but never cited")

    if FAILS:
        print("\n".join(FAILS))
        print(f"{len(FAILS)} problem(s) in {path.name}")
        sys.exit(1)
    print(f"OK {path.name}: {len(rows)} sources, all cited; every finding has a source (this does not judge the claims)")


if __name__ == "__main__":
    main()
