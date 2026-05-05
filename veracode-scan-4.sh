#!/usr/bin/env bash
#
# veracode-scan.sh
#
# Wrapper-only Veracode sandbox scan. No curl, no HMAC, no Python.
# All Veracode interaction goes through the Java wrapper JAR with auth
# via VERACODE_API_KEY_ID / VERACODE_API_KEY_SECRET env vars.

set -euo pipefail

: "${VERACODE_API_KEY_ID:?required}"
: "${VERACODE_API_KEY_SECRET:?required}"
: "${VERACODE_APP_ID:?required}"
: "${VERACODE_APP_NAME:?required}"
: "${SANDBOX_ID:?required}"
: "${SANDBOX_NAME:?required}"
: "${ARTIFACT_PATH:?required}"
: "${GITHUB_OUTPUT:?required}"
: "${RUNNER_TEMP:?required}"

: "${FAIL_ON_POLICY:=true}"
: "${FAIL_WORKFLOW_ON_ERROR:=true}"
: "${POLL_INTERVAL_SECONDS:=60}"
: "${POLL_TIMEOUT_SECONDS:=3600}"
: "${VERACODE_WRAPPER_JAR:=${RUNNER_TEMP}/VeracodeJavaAPI.jar}"
: "${SCAN_VERSION:=${GITHUB_RUN_ID:-manual-$(date +%s)}}"

echo "::add-mask::${VERACODE_API_KEY_SECRET}"

SCAN_FAILED="false"
POLICY_VIOLATION="false"
BUILD_ID=""

write_outputs() {
  {
    echo "scan_failed=${SCAN_FAILED}"
    echo "policy_violation=${POLICY_VIOLATION}"
    echo "build_id=${BUILD_ID}"
  } >> "$GITHUB_OUTPUT"
}
trap write_outputs EXIT

vc_wrapper() {
  java -jar "$VERACODE_WRAPPER_JAR" "$@"
}

# --- Preflight ------------------------------------------------------------
if [[ ! -f "$VERACODE_WRAPPER_JAR" ]]; then
  echo "::error::Veracode wrapper JAR not found at: $VERACODE_WRAPPER_JAR"
  SCAN_FAILED="true"
  [[ "${FAIL_WORKFLOW_ON_ERROR,,}" == "true" ]] && exit 1 || exit 0
fi

shopt -s nullglob
artifacts=( $ARTIFACT_PATH )
shopt -u nullglob
if (( ${#artifacts[@]} == 0 )); then
  echo "::error::No artifacts matched ARTIFACT_PATH: $ARTIFACT_PATH"
  SCAN_FAILED="true"
  [[ "${FAIL_WORKFLOW_ON_ERROR,,}" == "true" ]] && exit 1 || exit 0
fi
echo "::notice::Found ${#artifacts[@]} artifact(s) to upload"

# --- Submit ---------------------------------------------------------------
echo "::group::Submitting Veracode scan"
echo "App: ${VERACODE_APP_NAME} (id: ${VERACODE_APP_ID})"
echo "Sandbox: ${SANDBOX_NAME} (id: ${SANDBOX_ID})"
echo "Version: ${SCAN_VERSION}"
echo "Artifacts: ${artifacts[*]}"

submit_log="${RUNNER_TEMP}/veracode-submit.log"

set +e
vc_wrapper \
  -action uploadandscan \
  -appname "$VERACODE_APP_NAME" \
  -sandboxname "$SANDBOX_NAME" \
  -createsandbox false \
  -version "$SCAN_VERSION" \
  -filepath "${artifacts[@]}" \
  -scantimeout 0 \
  -autoscan true \
  2>&1 | tee "$submit_log"
submit_rc=${PIPESTATUS[0]}
set -e
echo "::endgroup::"

if (( submit_rc != 0 )); then
  echo "::error::Veracode wrapper exited with code ${submit_rc} during submit"
  SCAN_FAILED="true"
  [[ "${FAIL_WORKFLOW_ON_ERROR,,}" == "true" ]] && exit 1 || exit 0
fi

# --- Resolve build_id -----------------------------------------------------
BUILD_ID=$(grep -oP 'build_id="\K[^"]+' "$submit_log" | head -1 || true)

if [[ -z "$BUILD_ID" ]]; then
  echo "::warning::Could not parse build_id from wrapper output; querying via getbuildinfo"
  build_xml=$(vc_wrapper -action getbuildinfo \
    -appid "$VERACODE_APP_ID" \
    -sandboxid "$SANDBOX_ID" 2>/dev/null || echo "")
  BUILD_ID=$(grep -oP 'build_id="\K[^"]+' <<<"$build_xml" | head -1 || true)
fi

if [[ -z "$BUILD_ID" ]]; then
  echo "::error::Could not determine build_id; cannot poll"
  SCAN_FAILED="true"
  [[ "${FAIL_WORKFLOW_ON_ERROR,,}" == "true" ]] && exit 1 || exit 0
fi
echo "::notice::Submitted. build_id=${BUILD_ID}"

# --- Poll -----------------------------------------------------------------
echo "::group::Polling for scan completion"
elapsed=0
final_status=""

while (( elapsed < POLL_TIMEOUT_SECONDS )); do
  sleep "$POLL_INTERVAL_SECONDS"
  elapsed=$(( elapsed + POLL_INTERVAL_SECONDS ))

  build_xml=$(vc_wrapper -action getbuildinfo \
    -appid "$VERACODE_APP_ID" \
    -buildid "$BUILD_ID" 2>/dev/null || echo "")

  status=$(grep -oP 'analysis_unit[^>]*status="\K[^"]+' <<<"$build_xml" | head -1)
  echo "[${elapsed}s] status: ${status:-unknown}"

  case "${status,,}" in
    "results ready")
      final_status="$status"
      break
      ;;
    "scan cancelled"|"pre-scan failed"|"no modules defined"|"incomplete")
      echo "::error::Scan ended in non-success state: ${status}"
      SCAN_FAILED="true"
      [[ "${FAIL_WORKFLOW_ON_ERROR,,}" == "true" ]] && exit 1 || exit 0
      ;;
  esac
done
echo "::endgroup::"

if [[ -z "$final_status" ]]; then
  echo "::error::Polling timed out after ${POLL_TIMEOUT_SECONDS}s"
  SCAN_FAILED="true"
  [[ "${FAIL_WORKFLOW_ON_ERROR,,}" == "true" ]] && exit 1 || exit 0
fi

# --- Policy check ---------------------------------------------------------
echo "::group::Checking policy compliance"
report_xml=$(vc_wrapper -action detailedreport -buildid "$BUILD_ID")

policy_compliance=$(grep -oP 'policy_compliance_status="\K[^"]+' <<<"$report_xml" | head -1)
echo "Policy compliance: ${policy_compliance:-unknown}"

case "${policy_compliance,,}" in
  "pass"|"conditional pass")
    echo "::notice::Policy passed"
    ;;
  *)
    POLICY_VIOLATION="true"
    echo "::warning::Policy violation: ${policy_compliance}"
    if [[ "${FAIL_ON_POLICY,,}" == "true" ]]; then
      echo "::error::Failing workflow because fail_on_policy_violation=true"
      echo "::endgroup::"
      exit 1
    fi
    ;;
esac
echo "::endgroup::"

echo "::notice::Scan complete. policy=${policy_compliance} build_id=${BUILD_ID}"
