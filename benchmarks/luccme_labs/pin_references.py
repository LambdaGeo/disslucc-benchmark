#!/usr/bin/env python3
"""Re-pin references.toml to a ref (tag or commit) of a local luccme-goldens clone.

    python benchmarks/luccme_labs/pin_references.py --goldens ../luccme-goldens --ref v1.1.0 \\
        --doi 10.5281/zenodo.23161342
    python benchmarks/luccme_labs/pin_references.py --goldens ../luccme-goldens --ref v1.1.0 --dry-run

Keeps the list of files already in references.toml and rewrites `ref`, `commit`, `doi` and the
SHA-256 of every file, read with `git show <ref>:<path>` so a hash can never describe bytes that
are not at that ref. Nothing is copied by hand.
"""
from __future__ import annotations

import argparse
import hashlib
import re
import subprocess
import sys
from pathlib import Path

TOML = Path(__file__).resolve().parent / "references.toml"
URL = "https://raw.githubusercontent.com/LambdaGeo/luccme-goldens/{ref}/{path}"


def git(clone: Path, *args: str) -> bytes:
    r = subprocess.run(["git", "-C", str(clone), *args], capture_output=True)
    if r.returncode:
        sys.exit(f"git {' '.join(args)}: {r.stderr.decode().strip()}")
    return r.stdout


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--goldens", required=True, help="path to a local clone of LambdaGeo/luccme-goldens")
    ap.add_argument("--ref", required=True, help="tag or commit to pin, e.g. v1.1.0")
    ap.add_argument("--doi", default=None, help="Zenodo DOI of that release, if any")
    ap.add_argument("--dry-run", action="store_true", help="print what would change, write nothing")
    a = ap.parse_args()
    clone = Path(a.goldens)

    old = TOML.read_text()
    paths = re.findall(r'^"([^"]+)" = "[0-9a-f]{64}"', old, re.M)
    commit = git(clone, "rev-parse", f"{a.ref}^{{commit}}").decode().strip()
    new = {p: hashlib.sha256(git(clone, "show", f"{a.ref}:{p}")).hexdigest() for p in paths}
    was = dict(re.findall(r'^"([^"]+)" = "([0-9a-f]{64})"', old, re.M))
    changed = [p for p in paths if was[p] != new[p]]

    lines = [
        "# Pinned references: files fetched from LambdaGeo/luccme-goldens at an exact ref.",
        "# Every file is verified by SHA-256 before use (see references.py).",
        "# Regenerate with pin_references.py; do not edit the hashes by hand.",
        "",
        "[source]",
        'repo = "LambdaGeo/luccme-goldens"',
        f'ref = "{a.ref}"',
        f'commit = "{commit}"',
    ]
    if a.doi:
        lines.append(f'doi = "{a.doi}"')
    lines += [f'url = "{URL}"', "", "[files]"] + [f'"{p}" = "{new[p]}"' for p in paths]
    print(f"ref {a.ref} -> {commit[:12]}; {len(paths)} files, {len(changed)} with a new hash")
    for p in changed:
        print("  changed:", p)
    if not a.dry_run:
        TOML.write_text("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
