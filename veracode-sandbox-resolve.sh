#!/usr/bin/env bash
#
# veracode-sandbox-resolve.sh
#
# Resolves a Veracode sandbox to use for the current scan:
#   1. Lists existing sandboxes for the app
#   2. For each, checks the latest scan status
#   3. Returns the first idle sandbox (no scan, or last scan in terminal state)
#   4. If none are idle and we're under the 10-sandbox cap, creates a new one
#   5. If at the cap and all are busy, exits non-zero (caller decides: wait or fail)
#
# Outputs to GITHUB_OUTPUT:
#   sandbox_id   - numeric Veracode sandbox ID
#   sandbox_name - human-readable name
#   created      - "true" if newly created, "false" if reused
#
# Required env:
#   VERACODE_API_ID, VERACODE_API_KEY  - HMAC creds (use veracode/veracode-hmac-helper or similar)
#   VERACODE_APP_ID                    - numeric application ID
#   SANDBOX_NAME_PREFIX                - e.g. "ci-" -- new sandboxes get "<prefix><run_id>"
#   GITHUB_RUN_ID                      - used to name new sandboxes uniquely

set -euo pipefail

: "${VERACODE_API_ID:?required}"
: "${VERACODE_API_KEY:?required}"
: "${VERACODE_APP_ID:?required}"
: "${SANDBOX_NAME_PREFIX:=ci-}"
: "${GITHUB_RUN_ID:?required}"

readonly MAX_SANDBOXES=10
readonly API_BASE="https://analysiscenter.veracode.com/api"

# --- HMAC auth helper -------------------------------------------------------
# Veracode uses HMAC-SHA256 over (id + ts + nonce + URL + method).
# In real use, prefer the official veracode-hmac-helper; this is illustrative.
veracode_curl() {
  local method="$1" path="$2"
  # Assumes you have an `hmac_auth_header` function or use the helper:
  #   curl -H "Authorization: $(generate_hmac "$method" "$path")" ...
  curl --silent --fail --show-error \
    -H "Authorization: $(generate_hmac "$method" "$path")" \
    -X "$method" \
    "${API_BASE}${path}"
}

# --- Step 1: list sandboxes -------------------------------------------------
list_sandboxes_json() {
  # XML API still authoritative for sandbox metadata; convert to JSON for jq.
  # Or use REST: GET /appsec/v1/applications/{guid}/sandboxes
  veracode_curl GET "/5.0/getsandboxlist.do?app_id=${VERACODE_APP_ID}" \
    | xq -c '.'  # python-yq's xq: XML -> JSON
}

# --- Step 2: check if a sandbox is idle ------------------------------------
# A sandbox is "idle" if its latest build is in a terminal state:
#   "Results Ready", "No Modules Defined", "Incomplete", "Scan Cancelled",
#   "Pre-Scan Failed", or no build exists at all.
# Busy states include:
#   "Submitted to Engine", "Scan in Process", "Pre-Scan Submitted",
#   "Pre-Scan Success" (waiting on scan start), "Uploading"
is_sandbox_idle() {
  local sandbox_id="$1"
  local build_info
  build_info=$(veracode_curl GET \
    "/5.0/getbuildinfo.do?app_id=${VERACODE_APP_ID}&sandbox_id=${sandbox_id}" \
    2>/dev/null || echo "")

  # No build yet => idle
  if [[ -z "$build_info" ]] || ! grep -q '<build ' <<<"$build_info"; then
    return 0
  fi

  local status
  status=$(grep -oP 'analysis_unit[^>]*status="\K[^"]+' <<<"$build_info" | head -1)

  case "${status,,}" in
    "results ready"|"no modules defined"|"incomplete"|"scan cancelled"|"pre-scan failed"|"")
      return 0   # idle
      ;;
    *)
      return 1   # busy
      ;;
  esac
}

# --- Step 3: find first idle sandbox ----------------------------------------
find_idle_sandbox() {
  local list_xml
  list_xml=$(veracode_curl GET "/5.0/getsandboxlist.do?app_id=${VERACODE_APP_ID}")

  # Extract sandbox_id + sandbox_name pairs
  # Format: <sandbox sandbox_id="123" sandbox_name="ci-foo" .../>
  local pairs
  pairs=$(grep -oP 'sandbox_id="\K[^"]+' <<<"$list_xml" || true)

  local count=0
  while IFS= read -r sid; do
    [[ -z "$sid" ]] && continue
    count=$((count + 1))
    local sname
    sname=$(grep -oP "sandbox_id=\"${sid}\"[^>]*sandbox_name=\"\K[^\"]+" <<<"$list_xml")

    echo "::debug::Checking sandbox ${sid} (${sname})"
    if is_sandbox_idle "$sid"; then
      echo "::notice::Reusing idle sandbox ${sid} (${sname})"
      printf '%s\t%s\t%s\n' "$sid" "$sname" "false"
      return 0
    fi
  done <<<"$pairs"

  # None idle -- return current count so caller can decide create vs wait
  printf 'COUNT=%s\n' "$count"
  return 1
}

# --- Step 4: create new sandbox --------------------------------------------
create_sandbox() {
  local new_name="${SANDBOX_NAME_PREFIX}${GITHUB_RUN_ID}"
  echo "::notice::Creating new sandbox: ${new_name}"

  local resp
  resp=$(veracode_curl POST \
    "/5.0/createsandbox.do?app_id=${VERACODE_APP_ID}&sandbox_name=${new_name}")

  local new_id
  new_id=$(grep -oP 'sandbox_id="\K[^"]+' <<<"$resp" | head -1)

  if [[ -z "$new_id" ]]; then
    echo "::error::Failed to create sandbox. Response: $resp" >&2
    return 1
  fi

  printf '%s\t%s\t%s\n' "$new_id" "$new_name" "true"
}

# --- Main resolution flow ---------------------------------------------------
main() {
  local result
  if result=$(find_idle_sandbox); then
    # Idle found
    IFS=$'\t' read -r sid sname created <<<"$result"
  else
    # Parse count from the marker line
    local current_count
    current_count=$(grep -oP 'COUNT=\K\d+' <<<"$result" || echo "0")

    if (( current_count >= MAX_SANDBOXES )); then
      echo "::error::All ${MAX_SANDBOXES} sandboxes are busy. Caller should wait/retry." >&2
      echo "all_busy=true" >> "$GITHUB_OUTPUT"
      exit 2   # distinct exit code so workflow can branch on "wait" vs "hard fail"
    fi

    if ! result=$(create_sandbox); then
      exit 1
    fi
    IFS=$'\t' read -r sid sname created <<<"$result"
  fi

  {
    echo "sandbox_id=${sid}"
    echo "sandbox_name=${sname}"
    echo "created=${created}"
  } >> "$GITHUB_OUTPUT"

  echo "Resolved sandbox: id=${sid} name=${sname} created=${created}"
}

main "$@"
