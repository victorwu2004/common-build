#!/usr/bin/env bash
#
# veracode-sandbox-resolve-wrapper.sh
#
# Pure wrapper-based sandbox resolution. No curl, no HMAC, no Python.
# Uses the Java wrapper JAR for all Veracode interactions.

set -euo pipefail

: "${VERACODE_API_ID:?required}"
: "${VERACODE_API_KEY:?required}"
: "${VERACODE_APP_NAME:?required}"
: "${GITHUB_RUN_ID:?required}"
: "${GITHUB_OUTPUT:?required}"
: "${RUNNER_TEMP:?required}"

: "${SANDBOX_NAME_PREFIX:=ci-}"
: "${VERACODE_WRAPPER_JAR:=${RUNNER_TEMP}/VeracodeJavaAPI.jar}"
: "${MAX_SANDBOXES:=10}"

# Wrapper auth via env vars -- no CLI flag, no ps leak
export VERACODE_API_KEY_ID="${VERACODE_API_ID}"
export VERACODE_API_KEY_SECRET="${VERACODE_API_KEY}"

echo "::add-mask::${VERACODE_API_KEY}"

vc_wrapper() {
  java -jar "$VERACODE_WRAPPER_JAR" "$@"
}

# --- Step 1: Get app ID from name (wrapper needs it for some calls) -------
APP_LIST_XML=$(vc_wrapper -action getapplist)
APP_ID=$(grep -oP "app_name=\"${VERACODE_APP_NAME}\"[^>]*app_id=\"\K[^\"]+" <<<"$APP_LIST_XML" \
       || grep -oP "app_id=\"\K[^\"]+(?=\"[^>]*app_name=\"${VERACODE_APP_NAME}\")" <<<"$APP_LIST_XML" \
       || true)

if [[ -z "$APP_ID" ]]; then
  echo "::error::Could not find app_id for '${VERACODE_APP_NAME}'"
  exit 1
fi
echo "::notice::Resolved app_id=${APP_ID} for ${VERACODE_APP_NAME}"

# --- Step 2: List existing sandboxes --------------------------------------
SANDBOX_LIST_XML=$(vc_wrapper -action getsandboxlist -appid "$APP_ID")

# Parse sandbox name + id pairs into a temp file (one per line: id<TAB>name)
SANDBOX_FILE="${RUNNER_TEMP}/sandboxes.tsv"
: > "$SANDBOX_FILE"

# Match sandbox elements; order of attrs varies, so grab whole element
while IFS= read -r line; do
  sid=$(grep -oP 'sandbox_id="\K[^"]+' <<<"$line" || true)
  sname=$(grep -oP 'sandbox_name="\K[^"]+' <<<"$line" || true)
  if [[ -n "$sid" && -n "$sname" ]]; then
    printf '%s\t%s\n' "$sid" "$sname" >> "$SANDBOX_FILE"
  fi
done < <(grep -oE '<sandbox [^/]*/>' <<<"$SANDBOX_LIST_XML")

CURRENT_COUNT=$(wc -l < "$SANDBOX_FILE")
echo "::notice::Found ${CURRENT_COUNT} existing sandboxes"

# --- Step 3: Find first idle sandbox --------------------------------------
SANDBOX_ID=""
SANDBOX_NAME=""
CREATED="false"

while IFS=$'\t' read -r sid sname; do
  [[ -z "$sid" ]] && continue

  # Use wrapper getbuildinfo to check status
  build_xml=$(vc_wrapper -action getbuildinfo -appid "$APP_ID" -sandboxid "$sid" 2>/dev/null || echo "")

  # No build = idle
  if [[ -z "$build_xml" ]] || ! grep -q '<build ' <<<"$build_xml"; then
    SANDBOX_ID="$sid"
    SANDBOX_NAME="$sname"
    echo "::notice::Reusing empty sandbox ${sid} (${sname})"
    break
  fi

  status=$(grep -oP 'analysis_unit[^>]*status="\K[^"]+' <<<"$build_xml" | head -1)

  case "${status,,}" in
    "results ready"|"no modules defined"|"incomplete"|"scan cancelled"|"pre-scan failed"|"")
      SANDBOX_ID="$sid"
      SANDBOX_NAME="$sname"
      echo "::notice::Reusing idle sandbox ${sid} (${sname}) [last status: ${status}]"
      break
      ;;
    *)
      echo "::debug::Sandbox ${sid} busy [${status}]"
      ;;
  esac
done < "$SANDBOX_FILE"

# --- Step 4: Create new if none idle and under cap ------------------------
if [[ -z "$SANDBOX_ID" ]]; then
  if (( CURRENT_COUNT >= MAX_SANDBOXES )); then
    echo "::error::All ${MAX_SANDBOXES} sandboxes busy, cannot create more"
    {
      echo "all_busy=true"
      echo "sandbox_id="
      echo "sandbox_name="
      echo "created=false"
    } >> "$GITHUB_OUTPUT"
    exit 2
  fi

  NEW_NAME="${SANDBOX_NAME_PREFIX}${GITHUB_RUN_ID}"
  echo "::notice::Creating new sandbox: ${NEW_NAME}"

  CREATE_XML=$(vc_wrapper -action createsandbox -appid "$APP_ID" -sandboxname "$NEW_NAME")
  SANDBOX_ID=$(grep -oP 'sandbox_id="\K[^"]+' <<<"$CREATE_XML" | head -1)
  SANDBOX_NAME="$NEW_NAME"
  CREATED="true"

  if [[ -z "$SANDBOX_ID" ]]; then
    echo "::error::Failed to create sandbox. Response: $CREATE_XML"
    exit 1
  fi
fi

# --- Outputs --------------------------------------------------------------
{
  echo "sandbox_id=${SANDBOX_ID}"
  echo "sandbox_name=${SANDBOX_NAME}"
  echo "app_id=${APP_ID}"
  echo "created=${CREATED}"
  echo "all_busy=false"
} >> "$GITHUB_OUTPUT"

echo "Resolved: id=${SANDBOX_ID} name=${SANDBOX_NAME} created=${CREATED}"
