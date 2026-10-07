#!/bin/sh
# Run this on a machine WITH internet access. It downloads everything the whole
# course needs into offline-bundle/, so the lab machine never has to go online.
#
# Run it on a machine with the SAME OS family, CPU type and Python version as the
# lab machine (easiest: the lab machine itself, while it is still online).
set -e
cd "$(dirname "$0")/.."

TERRAFORM_VERSION="1.16.5"
IOSXE_PROVIDER_VERSION="1.1.1"
UTILS_PROVIDER_VERSION="2.0.3"
LOCAL_PROVIDER_VERSION="2.9.1"
NAC_IOSXE_MODULE_VERSION="1.0.0"

case "$(uname -m)" in
  x86_64)  TF_ARCH="amd64" ;;
  aarch64|arm64) TF_ARCH="arm64" ;;
  *) echo "Unsupported CPU: $(uname -m)" >&2; exit 1 ;;
esac

BUNDLE="offline-bundle"
mkdir -p "$BUNDLE/wheels" "$BUNDLE/bin" "$BUNDLE/terraform-mirror" "$BUNDLE/modules"

echo "==> 1/4 Python packages"
python3 -m pip download -r requirements.txt -d "$BUNDLE/wheels"
python3 -m pip download -r requirements-later.txt -d "$BUNDLE/wheels"

echo "==> 2/4 Terraform $TERRAFORM_VERSION (linux_$TF_ARCH)"
ZIP="terraform_${TERRAFORM_VERSION}_linux_${TF_ARCH}.zip"
BASE="https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}"
curl -fsSL -o "$BUNDLE/$ZIP" "$BASE/$ZIP"
curl -fsSL -o "$BUNDLE/terraform_SHA256SUMS" "$BASE/terraform_${TERRAFORM_VERSION}_SHA256SUMS"
( cd "$BUNDLE" && grep " $ZIP\$" terraform_SHA256SUMS | sha256sum -c - )
unzip -o -q "$BUNDLE/$ZIP" terraform -d "$BUNDLE/bin"
chmod +x "$BUNDLE/bin/terraform"
rm -f "$BUNDLE/$ZIP" "$BUNDLE/terraform_SHA256SUMS"

echo "==> 3/4 Terraform providers (iosxe, utils, local)"
WORK="$(mktemp -d)"
cat > "$WORK/main.tf" <<EOF
terraform {
  required_providers {
    iosxe = { source = "CiscoDevNet/iosxe", version = "= ${IOSXE_PROVIDER_VERSION}" }
    utils = { source = "netascode/utils",   version = "= ${UTILS_PROVIDER_VERSION}" }
    local = { source = "hashicorp/local",   version = "= ${LOCAL_PROVIDER_VERSION}" }
  }
}
EOF
( cd "$WORK" && "$OLDPWD/$BUNDLE/bin/terraform" providers mirror -platform="linux_${TF_ARCH}" "$OLDPWD/$BUNDLE/terraform-mirror" )
rm -rf "$WORK"

echo "==> 4/4 nac-iosxe Terraform module $NAC_IOSXE_MODULE_VERSION"
curl -fsSL -o "$BUNDLE/nac-iosxe.tar.gz" \
  "https://github.com/netascode/terraform-iosxe-nac-iosxe/archive/refs/tags/v${NAC_IOSXE_MODULE_VERSION}.tar.gz"
rm -rf "$BUNDLE/modules/nac-iosxe"
mkdir -p "$BUNDLE/modules/nac-iosxe"
tar -xzf "$BUNDLE/nac-iosxe.tar.gz" -C "$BUNDLE/modules/nac-iosxe" --strip-components=1
rm -f "$BUNDLE/nac-iosxe.tar.gz"

echo
echo "Done. Copy this whole folder (offline-bundle/ included) to the offline lab machine."
du -sh "$BUNDLE"
