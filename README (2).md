# Veracode Pipeline Scan — Composite Action (Linux / `java -jar`)

A GitHub Actions composite action that runs a Veracode **Pipeline Scan** (SAST) by
invoking `java -jar pipeline-scan.jar` on a self-hosted **Linux** runner. It resolves
the scanner jar (pre-staged or downloaded), runs a pre-flight reachability check,
routes the JVM through your HTTPS proxy to reach `api.veracode.com`, and translates the
scanner's exit code into a clear pass / warn / fail.

All steps use `shell: bash`.

---

## The one thing to understand first

Pipeline Scan does **not** use `analysiscenter.veracode.com`. Its REST API is served
only from `api.veracode.com`, and the host is fixed by region — there is no flag to
repoint it. If your network only allows `analysiscenter.veracode.com` directly, the jar
must reach `api.veracode.com` through a proxy.

| Host | Used by | Purpose |
|------|---------|---------|
| `api.veracode.com` | **Pipeline Scan jar** | Scan auth, upload, submit, findings (REST + HMAC) |
| `analysiscenter.veracode.com` | Upload-and-Scan wrapper | XML / Platform APIs |
| `downloads.veracode.com` | (optional) | Downloading `pipeline-scan-LATEST.zip` |

If you cannot proxy to `api.veracode.com`, Pipeline Scan is not an option — use
**Upload-and-Scan**, which is built for `analysiscenter.veracode.com`.

---

## How the action works

1. **Resolve jar** — if `jar-path` points at an existing `pipeline-scan.jar`, it's used
   as-is. Otherwise the action downloads `jar-url` (through the proxy) and extracts it.
2. **Pre-flight** — verifies the artifact exists and that the proxy can reach
   `api.veracode.com/healthcheck/status`, failing fast (seconds) instead of after a long
   scan timeout.
3. **Scan** — builds the JVM proxy/truststore flags, runs `java -jar pipeline-scan.jar`,
   captures the exit code, and applies the pass / warn / fail logic.

---

## Prerequisites

- Self-hosted Linux runner with **JDK 8+**, plus `curl` and `unzip` (needed only if the
  action downloads the jar; not needed when `jar-path` is supplied).
- Network path to `api.veracode.com:443` via your proxy.
- Veracode **API service account** with the *Upload and Scan API* or
  *Upload API – Submit Only* role; store ID/key as secrets.
- For TLS-inspecting proxies (Zscaler): the proxy root CA imported into a **Java
  truststore** (the JVM does not use the OS trust store).

---

## Usage

```yaml
jobs:
  security:
    runs-on: [self-hosted, linux]
    steps:
      - uses: actions/checkout@v4

      # get the built artifact from a previous job
      - uses: actions/download-artifact@v4
        with:
          name: app

      - uses: ./.github/actions/veracode-pipeline-scan-linux
        with:
          vid: ${{ secrets.VERACODE_API_ID }}
          vkey: ${{ secrets.VERACODE_API_KEY }}
          file: app.zip

          # jar: pre-stage from Nexus (recommended) OR let it download via proxy
          jar-path: ${{ github.workspace }}/tools/pipeline-scan.jar
          # jar-url: https://nexus.internal/repository/raw/veracode/pipeline-scan-LATEST.zip

          fail-on-severity: "Very High,High"
          # fail-on-cwe: "89,80"
          # baseline-file: baseline.json
          # timeout: "30"

          proxy-host: your.zscaler.proxy
          proxy-port: "9443"
          proxy-user: ${{ secrets.PROXY_USER }}          # only if proxy authenticates
          proxy-password: ${{ secrets.PROXY_PASS }}
          truststore-path: ${{ github.workspace }}/veracode-truststore.jks  # only if TLS-intercepted
          truststore-password: ${{ secrets.TRUSTSTORE_PASS }}

          fail-build: "false"        # findings warn instead of failing the job
```

---

## Inputs

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `vid` | yes | — | Veracode API ID (secret) |
| `vkey` | yes | — | Veracode API key (secret) |
| `file` | yes | — | Packaged artifact to scan (zip/jar/war/…) |
| `app-name` | no | `${{ github.repository }}` | Project name in scan output |
| `fail-on-severity` | no | `Very High,High` | Severities that count as findings |
| `fail-on-cwe` | no | `""` | Comma-separated CWE IDs to fail on |
| `baseline-file` | no | `""` | Baseline `results.json` for net-new findings |
| `timeout` | no | `30` | Max minutes to wait (Veracode hard cap is 60) |
| `jar-path` | no | `""` | Path to a pre-staged `pipeline-scan.jar`; skips download when set |
| `jar-url` | no | `downloads.veracode.com/…/pipeline-scan-LATEST.zip` | Where to download the jar; point at Nexus if `downloads.veracode.com` is blocked |
| `proxy-host` | no | `""` | Proxy host to reach `api.veracode.com` |
| `proxy-port` | no | `""` | Proxy port |
| `proxy-user` | no | `""` | Proxy username (if authenticated) |
| `proxy-password` | no | `""` | Proxy password (secret) |
| `truststore-path` | no | `""` | Java truststore containing the proxy/Zscaler CA |
| `truststore-password` | no | `""` | Truststore password (secret) |
| `fail-build` | no | `true` | `true` fails the job on findings; `false` warns only |

> Although most proxy/truststore inputs are technically optional, in a restricted
> network `proxy-host`/`proxy-port` (and usually the truststore) are required for the
> jar to reach `api.veracode.com`.

## Outputs

| Output | Description |
|--------|-------------|
| `results-file` | Path to `results.json` |
| `exit-code` | Raw `pipeline-scan` exit code |
| `scan-passed` | `true` when the exit code is 0 |

Consume them downstream:

```yaml
      - uses: ./.github/actions/veracode-pipeline-scan-linux
        id: veracode
        with: { ... }
      - run: echo "Veracode exit code was ${{ steps.veracode.outputs.exit-code }}"
```

---

## Exit codes

| Code | Meaning |
|------|---------|
| `0` | No findings at/above the fail criteria |
| `1`–`200` | Number of findings (capped at 200) |
| `255` | Scan **did not complete** — connection / TLS / proxy-auth / credential error. **Not** a findings result. |

`fail-on-severity` and `fail-on-cwe` only decide *which flaws count toward the exit
code*. They do not decide whether the workflow fails — GitHub fails the step on any
non-zero exit. Use `fail-build` to change that.

---

## Proxy & TLS (why these flags exist)

The JVM does **not** read `HTTP_PROXY` / `HTTPS_PROXY` env vars (`curl` does). The scan
only goes through the proxy when these flags are passed — the action builds them from
your inputs:

```
-Dhttps.proxyHost=…  -Dhttps.proxyPort=…
-Dhttp.proxyHost=…   -Dhttp.proxyPort=…
-Dhttp.nonProxyHosts=
```

Authenticated proxy — Basic auth over the HTTPS CONNECT tunnel is disabled by default
since JDK 8u111, so the action re-enables it when `proxy-user` is set:

```
-Djdk.http.auth.tunneling.disabledSchemes=
-Djdk.http.auth.proxying.disabledSchemes=
```

TLS interception (Zscaler) — import the proxy root CA into a Java truststore and pass
`truststore-path` / `truststore-password`:

```bash
keytool -importcert -alias zscaler-root -file zscaler-root.cer \
        -keystore veracode-truststore.jks -storepass changeit -noprompt
```

> `curl` uses the OS trust store; the JVM uses its own. On Linux, `curl` may also need
> the CA in `/usr/local/share/ca-certificates/` (+ `update-ca-certificates`) to fetch
> the jar, but the **scan** only trusts what's in `truststore-path`.

---

## Warn-only (don't block the build)

Set `fail-build: "false"`. Findings (exit `1`–`200`) become a `::warning::` and the job
stays green, while a genuine tool error (e.g. `255`) still fails the step — so a broken
scan is never silently hidden. Prefer this over `continue-on-error: true`, which would
also swallow `255`.

---

## Troubleshooting

**Exit 255** — the scan never reached a verdict. Read the lines above the exit code:
- `UnknownHostException` / timeout → proxy isn't carrying the request to `api.veracode.com`.
- `SSLHandshakeException` / `PKIX path building failed` → Zscaler CA missing from the Java truststore.
- `401` → credentials (region mismatch, trailing whitespace, missing API role).
- Authenticated-proxy hang → the `disabledSchemes=` flags are missing.

**Quick path test** (same proxy the scan uses):
```bash
curl -sS -o /dev/null -w '%{http_code}\n' \
  -x http://PROXY:PORT https://api.veracode.com/healthcheck/status
# any HTTP status (even 401) means the path is open; an unsigned request is expected to 401
```

**`fail-build: false` but the job still fails on findings** — print the exit code first.
If the scan step is green but the job is red, the failure is a **downstream** step that
reads `results.json` (SARIF converter, "import findings" action, quality gate). Fix the
warn/fail behavior there.

**Errexit gotcha (direct `java -jar` steps)** — GitHub's `shell: bash` runs with `-e`,
which aborts the step the instant the jar returns non-zero. Capture the code with
`set +e; java …; code=$?` (or `java … && code=0 || code=$?`) before branching on it. The
action already does this internally.

**`unzip: command not found`** — only happens on the download path. Install `unzip`, or
supply `jar-path` to skip downloading entirely.

---

## Pipeline Scan vs Upload-and-Scan

| | Pipeline Scan | Upload-and-Scan |
|--|--------------|-----------------|
| Host | `api.veracode.com` | `analysiscenter.veracode.com` |
| Speed | Minutes, inline | Slower, system-of-record |
| Results | Ephemeral, not in Platform | Persisted under the app profile |
| Best for | Per-PR gating | Release / compliance scan of record |
