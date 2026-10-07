#!/bin/sh
# Run on the offline lab machine. Installs everything from offline-bundle/ only.
set -e
cd "$(dirname "$0")/.."
BUNDLE="$(pwd)/offline-bundle"

if [ ! -d "$BUNDLE/wheels" ]; then
  echo "offline-bundle/ not found - run prep/online_download_all.sh on a connected machine first." >&2
  exit 1
fi

python3 -m venv .venv
. .venv/bin/activate
python -m pip install --no-index --find-links "$BUNDLE/wheels" -r requirements.txt
if [ -f requirements-later.txt ]; then
  python -m pip install --no-index --find-links "$BUNDLE/wheels" -r requirements-later.txt
fi

# Terraform should read providers from the local mirror, never the internet.
cat > "$BUNDLE/terraform.rc" <<EOF
provider_installation {
  filesystem_mirror {
    path    = "$BUNDLE/terraform-mirror"
    include = ["registry.terraform.io/*/*"]
  }
  direct {
    exclude = ["registry.terraform.io/*/*"]
  }
}
EOF

echo
echo "Installed. In every new terminal run:   . prep/env.sh"
