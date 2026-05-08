#!/usr/bin/env bash
# test-pipeline-scan-endpoint.sh
# Verifies whether the Pipeline Scan JAR honors the veracode.api.base.url system property.
#
# Usage:
#   export VERACODE_API_ID=...
#   export VERACODE_API_KEY=...
#   export PIPELINE_JAR=/path/to/pipeline-scan.jar
#   export TEST_ARTIFACT=/path/to/small-app.zip
#   ./test-pipeline-scan-endpoint.sh

set -uo pipefail

: "${VERACODE_API_ID:?required}"
: "${VERACODE_API_KEY:?required}"
: "${PIPELINE_JAR:?path to pipeline-scan.jar required}"
: "${TEST_ARTIFACT:?path to a small artifact to scan required}"

CANDIDATE_HOSTS=(
  "https://analysiscenter.veracode.com/"
  "https://api.veracode.com/"
)

echo "=== Step 1: connectivity check ==="
for url in "${CANDIDATE_HOSTS[@]}"; do
  host=$(echo "$url" | awk -F/ '{print $3}')
  code=$(curl -sS -o /dev/null -w "%{http_code}" --max-time 10 "$url" 2>/dev/null || echo "TIMEOUT")
  echo "  $host -> HTTP $code"
done

echo
echo "=== Step 2: API ID region prefix ==="
case "$VERACODE_API_ID" in
  vera01ai-*) echo "  Prefix indicates: commercial (api.veracode.com default)" ;;
  vera01ei-*) echo "  Prefix indicates: european (api.veracode.eu default)" ;;
  *)          echo "  Unrecognized prefix: ${VERACODE_API_ID:0:10}..." ;;
esac

echo
echo "=== Step 3: scan with NO override (baseline) ==="
RESULTS_BASELINE=$(mktemp -t baseline.XXXXXX.json)
java -jar "$PIPELINE_JAR" \
  --veracode_api_id "$VERACODE_API_ID" \
  --veracode_api_key "$VERACODE_API_KEY" \
  --file "$TEST_ARTIFACT" \
  --json_output_file "$RESULTS_BASELINE" \
  --verbose true 2>&1 | tee /tmp/pipeline-baseline.log
BASELINE_EXIT=$?
echo "  Exit code: $BASELINE_EXIT"
echo "  Hosts contacted (from log):"
grep -oiE 'https?://[a-z0-9.-]+\.veracode\.[a-z]+' /tmp/pipeline-baseline.log | sort -u | sed 's/^/    /'

echo
echo "=== Step 4: scan WITH veracode.api.base.url=analysiscenter.veracode.com ==="
RESULTS_OVERRIDE=$(mktemp -t override.XXXXXX.json)
java -Dveracode.api.base.url=https://analysiscenter.veracode.com/ \
     -jar "$PIPELINE_JAR" \
  --veracode_api_id "$VERACODE_API_ID" \
  --veracode_api_key "$VERACODE_API_KEY" \
  --file "$TEST_ARTIFACT" \
  --json_output_file "$RESULTS_OVERRIDE" \
  --verbose true 2>&1 | tee /tmp/pipeline-override.log
OVERRIDE_EXIT=$?
echo "  Exit code: $OVERRIDE_EXIT"
echo "  Hosts contacted (from log):"
grep -oiE 'https?://[a-z0-9.-]+\.veracode\.[a-z]+' /tmp/pipeline-override.log | sort -u | sed 's/^/    /'

echo
echo "=== Verdict ==="
HOSTS_BASELINE=$(grep -oiE 'https?://[a-z0-9.-]+\.veracode\.[a-z]+' /tmp/pipeline-baseline.log | sort -u | tr '\n' ' ')
HOSTS_OVERRIDE=$(grep -oiE 'https?://[a-z0-9.-]+\.veracode\.[a-z]+' /tmp/pipeline-override.log | sort -u | tr '\n' ' ')

if [[ "$HOSTS_BASELINE" == "$HOSTS_OVERRIDE" ]]; then
  echo "  System property is IGNORED — same hosts contacted with and without override."
  echo "  Conclusion: this JAR version does not support endpoint override. Allowlist api.veracode.com."
elif [[ "$HOSTS_OVERRIDE" == *"analysiscenter.veracode.com"* ]] && [[ -s "$RESULTS_OVERRIDE" ]]; then
  echo "  System property is HONORED and scan completed via analysiscenter.veracode.com."
  echo "  Conclusion: you can use -Dveracode.api.base.url=https://analysiscenter.veracode.com/ in your composite."
else
  echo "  Override changed hosts but scan did not produce results."
  echo "  Conclusion: analysiscenter.veracode.com does not serve the Pipeline Scan REST API. Allowlist api.veracode.com."
fi
