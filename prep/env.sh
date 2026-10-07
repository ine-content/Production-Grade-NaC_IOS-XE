# Source this in every new terminal:   . prep/env.sh
_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")/.." && pwd)"
. "$_ROOT/.venv/bin/activate"
export PATH="$_ROOT/offline-bundle/bin:$PATH"
export TF_CLI_CONFIG_FILE="$_ROOT/offline-bundle/terraform.rc"
echo "NaC lab environment ready: $(terraform version | head -1), $(nac-validate --version)"
