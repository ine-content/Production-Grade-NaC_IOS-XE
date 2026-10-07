#!/usr/bin/env python3
"""Downloads the Terraform binary and the nac-iosxe module using only the Python standard library.

Usage:
  fetch_tools.py terraform <version> <amd64|arm64> <target-dir>
  fetch_tools.py module    <version> <target-dir>

Set TERRAFORM_BASE_URL or MODULE_BASE_URL to use an internal mirror instead of the public sites.
"""

import hashlib
import io
import os
import stat
import sys
import tarfile
import urllib.request
import zipfile
from pathlib import Path

TERRAFORM_BASE = os.environ.get("TERRAFORM_BASE_URL", "https://releases.hashicorp.com/terraform")
MODULE_BASE = os.environ.get(
    "MODULE_BASE_URL",
    "https://github.com/netascode/terraform-iosxe-nac-iosxe/archive/refs/tags",
)


def download(url):
    print(f"  downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as response:
        return response.read()


def fetch_terraform(version, arch, target):
    zip_name = f"terraform_{version}_linux_{arch}.zip"
    base = f"{TERRAFORM_BASE}/{version}"
    data = download(f"{base}/{zip_name}")
    sums = download(f"{base}/terraform_{version}_SHA256SUMS").decode()

    expected = None
    for line in sums.splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[1] == zip_name:
            expected = parts[0]
    if expected is None:
        sys.exit(f"No checksum listed for {zip_name}")
    actual = hashlib.sha256(data).hexdigest()
    if actual != expected:
        sys.exit(f"Checksum mismatch for {zip_name}: expected {expected}, got {actual}")
    print("  checksum ok")

    target = Path(target)
    target.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        binary = target / "terraform"
        binary.write_bytes(archive.read("terraform"))
    binary.chmod(binary.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    print(f"  installed {binary}")


def fetch_module(version, target):
    data = download(f"{MODULE_BASE}/v{version}.tar.gz")
    target = Path(target)
    if target.exists():
        import shutil
        shutil.rmtree(target)
    target.mkdir(parents=True)
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as archive:
        for member in archive.getmembers():
            parts = Path(member.name).parts[1:]   # drop the top-level folder
            if not parts or ".." in parts:
                continue
            member.name = str(Path(*parts))
            archive.extract(member, target)
    print(f"  unpacked module into {target}")


def main(argv):
    if len(argv) == 5 and argv[1] == "terraform":
        fetch_terraform(argv[2], argv[3], argv[4])
    elif len(argv) == 4 and argv[1] == "module":
        fetch_module(argv[2], argv[3])
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
