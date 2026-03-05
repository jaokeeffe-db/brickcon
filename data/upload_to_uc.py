"""
Upload mock data files to Unity Catalog Volumes using Databricks Connect.

Prerequisites:
  1. databricks-connect installed and configured (~/.databrickscfg or env vars)
  2. generate_mock_data.py has been run (files exist in data/output/)
  3. Unity Catalog setup (uc_setup.sql) has been run in the workspace
  4. Run `databricks auth login` first if using OAuth

Usage:
  python data/upload_to_uc.py
"""

import os
from pathlib import Path

from databricks.sdk import WorkspaceClient

# ---------------------------------------------------------------------------
# Configuration — override with environment variables if needed
# ---------------------------------------------------------------------------

CATALOG = os.getenv("UC_CATALOG", "utility_ops")
OUTPUT_DIR = Path(__file__).parent / "output"

TELEMETRY_VOLUME = f"/Volumes/{CATALOG}/raw_ingestion/raw_telemetry"
MANUALS_VOLUME = f"/Volumes/{CATALOG}/raw_ingestion/technical_manuals"

TELEMETRY_FILES = [
    "sensor_readings.csv",
    "maintenance_logs.csv",
    "asset_metadata.csv",
    "production_output.csv",
]

MANUALS_DIR = Path(__file__).parent.parent / "manuals"


def upload_file(client: WorkspaceClient, local_path: Path, volume_path: str) -> None:
    """Upload a single file to a UC Volume, overwriting if it exists."""
    dest = f"{volume_path}/{local_path.name}"
    print(f"  Uploading {local_path.name} → {dest} ...")
    with open(local_path, "rb") as f:
        client.files.upload(dest, f, overwrite=True)
    print(f"    ✓ {local_path.name} uploaded ({local_path.stat().st_size / 1024 / 1024:.1f} MB)")


def main() -> None:
    print("Connecting to Databricks workspace...")
    client = WorkspaceClient()
    print(f"  Connected: {client.config.host}")
    print()

    # Upload telemetry and reference data
    print(f"Uploading telemetry files to {TELEMETRY_VOLUME} ...")
    for filename in TELEMETRY_FILES:
        local = OUTPUT_DIR / filename
        if not local.exists():
            print(f"  WARN: {local} not found — run generate_mock_data.py first")
            continue
        upload_file(client, local, TELEMETRY_VOLUME)

    print()

    # Upload technical manuals
    if MANUALS_DIR.exists():
        print(f"Uploading technical manuals to {MANUALS_VOLUME} ...")
        for md_file in sorted(MANUALS_DIR.glob("*.md")):
            upload_file(client, md_file, MANUALS_VOLUME)
    else:
        print(f"WARN: manuals directory not found at {MANUALS_DIR}")

    print()
    print("All uploads complete.")
    print()

    # Verify by listing volume contents via SDK (no Spark session needed)
    print("Verifying — listing volume contents:")
    print()
    for volume_path in (TELEMETRY_VOLUME, MANUALS_VOLUME):
        print(f"  {volume_path}:")
        try:
            entries = list(client.files.list_directory_contents(volume_path))
            for entry in entries:
                size_kb = (entry.file_size or 0) / 1024
                print(f"    {entry.name:<45} {size_kb:>8.1f} KB")
        except Exception as e:
            print(f"    (could not list: {e})")
        print()


if __name__ == "__main__":
    main()
