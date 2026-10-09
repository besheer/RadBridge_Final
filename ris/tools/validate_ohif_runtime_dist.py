#!/usr/bin/env python3
"""Validate the deployed RadBridge OHIF distribution without a browser."""

import argparse
import hashlib
import json
from pathlib import Path
import re


class OhifContractError(RuntimeError):
    pass


REPORTING_MARKERS = (
    "RadBridge Reporting Workspace",
    "/radbridge-api/api/ohif/report",
    "ONLYOFFICE",
    "Browser Report Editor",
    "Save Draft",
    "DRAFT",
    "VERIFIED",
    "FINAL",
    "/lease/acquire",
    "/lease/release",
    "lease_token",
    "REPORT_LEASE_TOKEN_MISSING",
    "pagehide",
    "keepalive",
    "radbridgeReportWindow",
    "RB_ONLYOFFICE_WINDOW_REFERENCE_V1",
    "window.name",
    "popup=yes,width=1400",
    "Open ONLYOFFICE in New Window",
)


def _read(path):
    if not path.is_file():
        raise OhifContractError(f"MISSING_FILE:{path.name}")
    return path.read_text(encoding="utf-8", errors="ignore")


def _sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_dist(dist):
    dist = Path(dist).resolve()
    if not dist.is_dir():
        raise OhifContractError("OHIF_DIST_MISSING")

    index_path = dist / "index.html"
    config_path = dist / "app-config.js"
    index = _read(index_path)
    config = _read(config_path)

    branding = {
        "title": "<title>RadBridge | Diagnostic Imaging</title>" in index,
        "favicon_reference": "/assets/radbridge-favicon.svg" in index,
        "favicon_file": (dist / "assets" / "radbridge-favicon.svg").is_file(),
        "pacs_name": "RadBridge PACS" in config,
        "orthanc_name": "RadBridge Orthanc" in config,
    }
    missing_branding = [name for name, present in branding.items() if not present]
    if missing_branding:
        raise OhifContractError(
            "BRANDING_CONTRACT_MISSING:" + ",".join(missing_branding)
        )

    script_names = {
        Path(value).name
        for value in re.findall(r'src=["\']([^"\']+\.js)["\']', index)
    }
    missing_scripts = sorted(name for name in script_names if not (dist / name).is_file())
    if missing_scripts:
        raise OhifContractError("INDEX_SCRIPT_MISSING:" + ",".join(missing_scripts))

    candidates = []
    for path in sorted(dist.glob("*.js")):
        if path.name.endswith(".min.js"):
            continue
        text = _read(path)
        if (
            "RadBridge Reporting Workspace" in text
            and "/radbridge-api/api/ohif/report" in text
        ):
            candidates.append((path, text))
    if len(candidates) != 1:
        raise OhifContractError(
            f"REPORTING_BUNDLE_COUNT_INVALID:{len(candidates)}"
        )

    reporting_path, reporting = candidates[0]
    missing_markers = [item for item in REPORTING_MARKERS if item not in reporting]
    if missing_markers:
        raise OhifContractError(
            "REPORTING_CONTRACT_MISSING:" + ",".join(missing_markers)
        )

    return {
        "ok": True,
        "dist": str(dist),
        "index_sha256": _sha256(index_path),
        "app_config_sha256": _sha256(config_path),
        "app_config_size": config_path.stat().st_size,
        "reporting_bundle": reporting_path.name,
        "reporting_bundle_sha256": _sha256(reporting_path),
        "reporting_bundle_size": reporting_path.stat().st_size,
        "reporting_marker_count": len(REPORTING_MARKERS),
        "branding": branding,
        "index_script_count": len(script_names),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("dist")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    try:
        result = validate_dist(args.dist)
        if args.json:
            print(json.dumps(result, indent=2, sort_keys=True))
        else:
            print("OHIF_RUNTIME_CONTRACT=PASS")
            for key in (
                "reporting_bundle",
                "reporting_bundle_sha256",
                "app_config_size",
                "reporting_marker_count",
            ):
                print(f"{key.upper()}={result[key]}")
        return 0
    except OhifContractError as exc:
        print("OHIF_RUNTIME_CONTRACT=FAIL")
        print(f"ERROR={exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
