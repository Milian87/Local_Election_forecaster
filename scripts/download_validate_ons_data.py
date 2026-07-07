from __future__ import annotations

import argparse
import json
import subprocess
import sys
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ManifestFile:
    file_id: str
    label: str
    path: Path
    required: bool
    vintage: str | None
    download_url: str | None


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Download/validate ONS geography inputs from a manifest and optionally run "
            "the England boundary build pipeline."
        )
    )
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path("data") / "csv" / "ons_inputs_manifest.json",
        help="Path to JSON manifest defining ONS inputs and consistency rules.",
    )
    parser.add_argument(
        "--download-missing",
        action="store_true",
        help="Download missing files when download_url is present.",
    )
    parser.add_argument(
        "--build-after-validate",
        action="store_true",
        help="Run scripts/build_england_boundaries.py after validation succeeds.",
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=120,
        help="Download timeout in seconds.",
    )
    return parser.parse_args()


def load_manifest(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Manifest not found: {path}")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    if "files" not in data or not isinstance(data["files"], list):
        raise ValueError("Manifest must contain a 'files' list")
    return data


def parse_manifest_files(manifest: dict[str, Any], root_dir: Path) -> list[ManifestFile]:
    results: list[ManifestFile] = []
    for raw in manifest["files"]:
        file_id = str(raw["id"])
        label = str(raw.get("label", file_id))
        rel = Path(str(raw["path"]))
        required = bool(raw.get("required", True))
        vintage = str(raw["vintage"]) if raw.get("vintage") is not None else None
        download_url = str(raw["download_url"]).strip() if raw.get("download_url") else None

        results.append(
            ManifestFile(
                file_id=file_id,
                label=label,
                path=(root_dir / rel),
                required=required,
                vintage=vintage,
                download_url=download_url,
            )
        )
    return results


def check_shapefile_sidecars(shp_path: Path) -> list[str]:
    missing: list[str] = []
    if shp_path.suffix.lower() != ".shp":
        return missing

    for ext in [".dbf", ".shx", ".prj"]:
        if not shp_path.with_suffix(ext).exists():
            missing.append(str(shp_path.with_suffix(ext)))
    return missing


def download_file(url: str, dest: Path, timeout_seconds: int) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=timeout_seconds) as response:
        data = response.read()
    dest.write_bytes(data)


def validate_consistency(manifest: dict[str, Any], files_by_id: dict[str, ManifestFile]) -> list[str]:
    errors: list[str] = []
    groups = manifest.get("consistency_groups", [])
    for group in groups:
        name = str(group.get("name", "unnamed_group"))
        ids = [str(i) for i in group.get("file_ids", [])]
        require_same = bool(group.get("require_same_vintage", True))

        vintages: set[str] = set()
        for file_id in ids:
            mf = files_by_id.get(file_id)
            if mf is None:
                errors.append(f"Group '{name}' references unknown id: {file_id}")
                continue
            if mf.vintage is not None:
                vintages.add(mf.vintage)

        if require_same and len(vintages) > 1:
            errors.append(
                f"Group '{name}' has mixed vintages: {sorted(vintages)}"
            )

    return errors


def run_builder(root_dir: Path, files_by_id: dict[str, ManifestFile]) -> int:
    geometry_candidates = ["oa_boundaries_shp", "oa_boundaries_geojson"]
    geometry = None
    for candidate in geometry_candidates:
        mf = files_by_id.get(candidate)
        if mf is not None and mf.path.exists():
            geometry = mf.path
            break

    if geometry is None:
        raise FileNotFoundError(
            "No geometry source found. Expected one of: "
            + ", ".join(geometry_candidates)
        )

    lsoa_lookup = files_by_id["lsoa_to_ward_lad_lookup"].path
    ward_ced_lookup = files_by_id["ward_to_lad_county_ced_lookup"].path

    cmd = [
        sys.executable,
        str(root_dir / "scripts" / "build_england_boundaries.py"),
        "--geometry",
        str(geometry),
        "--lsoa-ward-lookup",
        str(lsoa_lookup),
        "--lookup",
        str(ward_ced_lookup),
    ]

    print("[STEP] Running boundary build pipeline")
    completed = subprocess.run(cmd, cwd=root_dir)
    return completed.returncode


def main() -> int:
    args = parse_args()
    root_dir = Path(__file__).resolve().parents[1]

    manifest_path = args.manifest
    if not manifest_path.is_absolute():
        manifest_path = root_dir / manifest_path

    print(f"[STEP] Loading manifest: {manifest_path}")
    manifest = load_manifest(manifest_path)
    manifest_files = parse_manifest_files(manifest, root_dir)
    files_by_id = {mf.file_id: mf for mf in manifest_files}

    errors: list[str] = []

    for mf in manifest_files:
        status = "found" if mf.path.exists() else "missing"
        print(f"[CHECK] {mf.label}: {status} -> {mf.path}")

        if not mf.path.exists() and mf.download_url and args.download_missing:
            try:
                print(f"[STEP] Downloading {mf.label}")
                download_file(mf.download_url, mf.path, args.timeout)
                print(f"[OK] Downloaded {mf.path}")
            except Exception as exc:
                errors.append(f"Download failed for '{mf.label}': {exc}")

        if mf.required and not mf.path.exists():
            errors.append(f"Required file missing: {mf.path}")

        if mf.path.exists():
            sidecar_missing = check_shapefile_sidecars(mf.path)
            for missing in sidecar_missing:
                errors.append(f"Missing shapefile sidecar: {missing}")

    errors.extend(validate_consistency(manifest, files_by_id))

    if errors:
        print("\n[FAILED] Validation errors detected:")
        for err in errors:
            print(f"- {err}")
        return 1

    print("\n[SUCCESS] All required ONS inputs are present and consistency checks passed.")

    if args.build_after_validate:
        required_ids = {"lsoa_to_ward_lad_lookup", "ward_to_lad_county_ced_lookup"}
        missing_ids = sorted(required_ids.difference(files_by_id.keys()))
        if missing_ids:
            print(f"[FAILED] Manifest missing required IDs for build step: {missing_ids}")
            return 1
        has_geometry_option = any(
            (files_by_id.get(candidate) is not None and files_by_id[candidate].path.exists())
            for candidate in ["oa_boundaries_shp", "oa_boundaries_geojson"]
        )
        if not has_geometry_option:
            print("[FAILED] Build step requires either oa_boundaries_shp or oa_boundaries_geojson.")
            return 1
        return run_builder(root_dir, files_by_id)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
