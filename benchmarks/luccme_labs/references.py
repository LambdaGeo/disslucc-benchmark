"""Fetch the pinned references from luccme-goldens, verified by SHA-256.

Nothing is stored in this repository: goldens, LuccME lab scripts and input layers are
downloaded from one exact commit of LambdaGeo/luccme-goldens (see references.toml) into a
local cache. A wrong or modified file fails here, before any metric is computed.
"""
from __future__ import annotations

import json
import tomllib
from pathlib import Path

import pooch

HERE = Path(__file__).resolve().parent
SPEC = tomllib.loads((HERE / "references.toml").read_text())
COMMIT = SPEC["source"]["commit"]
CACHE = Path(__import__("os").environ.get("DISSLUCC_BENCH_CACHE", HERE.parent.parent / ".cache" / "references"))

_POOCH = pooch.create(
    path=CACHE / COMMIT[:12],
    base_url=SPEC["source"]["url"].replace("{commit}", COMMIT).replace("{path}", ""),
    registry={path: f"sha256:{digest}" for path, digest in SPEC["files"].items()},
)


def fetch(path: str) -> Path:
    """Local path of a pinned file (downloaded on first use, hash-checked every time)."""
    if path not in SPEC["files"]:
        raise KeyError(f"{path} is not pinned in references.toml")
    return Path(_POOCH.fetch(path))


def lab_files(lab: str) -> dict[str, Path]:
    base = f"goldens/labs_per_year/{lab}"
    return {
        "golden": fetch(f"{base}/{lab}.csv.gz"),
        "manifest": fetch(f"{base}/manifest.json"),
        "log": fetch(f"{base}/terrame.log"),
        "lua": fetch(f"sources/labs/{lab}.lua"),
    }


def layer(name: str) -> Path:
    """Shapefile of an input layer (csAC, csAC_2009, cs_moju); sidecar files are fetched too."""
    for ext in ("dbf", "shx", "prj", "cpg"):
        if f"sources/labs/data/{name}.{ext}" in SPEC["files"]:
            fetch(f"sources/labs/data/{name}.{ext}")
    return fetch(f"sources/labs/data/{name}.shp")


def manifest(lab: str) -> dict:
    return json.loads(lab_files(lab)["manifest"].read_text())
