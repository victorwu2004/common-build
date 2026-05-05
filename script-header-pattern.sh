#!/usr/bin/env bash
#
# Reads everything from environment variables set by the composite action.
# Never accept secrets via CLI args -- they leak into `ps`, audit logs,
# and shell history.

set -euo pipefail

# Required -- fail loudly if missing
: "${VERACODE_API_ID:?must be set by composite action}"
: "${VERACODE_API_KEY:?must be set by composite action}"
: "${VERACODE_APP_ID:?must be set by composite action}"
: "${GITHUB_RUN_ID:?automatically set by GitHub Actions}"
: "${GITHUB_OUTPUT:?automatically set by GitHub Actions}"

# Optional with defaults
: "${SANDBOX_NAME_PREFIX:=ci-}"

# Defensive: re-mask in case the script is run outside a composite step
# (belt and suspenders -- the composite already handles this for `secrets.*`)
echo "::add-mask::${VERACODE_API_KEY}"

# ... rest of script unchanged ...
