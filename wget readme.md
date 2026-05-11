Good — wget is solid for this. Preserving the original filename via the `Content-Disposition` header lets you handle versioned JARs cleanly without hardcoding names.

## How wget preserves the filename

Two flags are the key:

- `--content-disposition` — honors the server's `Content-Disposition: attachment; filename="..."` header and saves under that name
- `--trust-server-names` — when following redirects, uses the final URL's basename rather than the original URL's basename

Use both together. Then capture the resulting filename for downstream steps.

```bash
cd "$WORK_DIR"
wget --content-disposition --trust-server-names \
     --user="$NEXUS_USER" --password="$NEXUS_PASSWORD" \
     -nv \
     "$URL"

# The downloaded file is now in $WORK_DIR with whatever name the server provided.
# Find it (most recently modified file in this dir):
DOWNLOADED=$(ls -t "$WORK_DIR" | head -1)
```

A few notes:

- `-nv` (non-verbose) keeps the log clean while still showing the resulting filename
- Don't use `-O <name>` — that **forces** a name and disables `--content-disposition`
- If Nexus doesn't send a `Content-Disposition` header (some raw repos don't), wget falls back to the URL basename, which is still better than a forced name

## Capturing the filename reliably

The "most recent file in directory" trick is fragile if anything else writes there. Cleaner approach: have wget write to an empty subdirectory, then enumerate.

```bash
DOWNLOAD_DIR="$RUNNER_TEMP/veracode-download"
mkdir -p "$DOWNLOAD_DIR"
cd "$DOWNLOAD_DIR"

wget --content-disposition --trust-server-names \
     --user="$NEXUS_USER" --password="$NEXUS_PASSWORD" \
     -nv \
     "$URL"

# Find the single jar/zip in the empty dir
FILES=( "$DOWNLOAD_DIR"/* )
if [[ ${#FILES[@]} -ne 1 ]]; then
  echo "::error::Expected exactly 1 file, got ${#FILES[@]}: ${FILES[*]}"
  exit 1
fi
DOWNLOADED="${FILES[0]}"
echo "Original filename: $(basename "$DOWNLOADED")"
```

Now `$DOWNLOADED` is the absolute path with the server's original filename preserved.

## Updated composite for the Veracode wrapper

Here's the wrapper composite (sandbox + policy modes) using wget with filename preservation, and threading the captured filename through all downstream steps:

## What changed and why

**wget replaces curl for the download.** `--content-disposition --trust-server-names` preserves whatever filename Nexus serves. No `-O` flag (which would force a name and break this).

**Empty download directory + single-file check.** The download step uses a fresh `$RUNNER_TEMP/veracode-wrapper-download/` so the resulting file is unambiguous. If anything other than exactly one file appears, it fails loudly. No "most recently modified" guesswork.

**Filename propagated as both `jar_path` (absolute path) and `jar_filename` (basename).** Other steps reference `${{ steps.download.outputs.jar_path }}` rather than hardcoded names. The basename is also output from the action itself in case downstream workflow steps need it (e.g. for caching, archiving, or audit).

**`wget` install step prepended.** Most Linux runners have it, but RHEL/UBI-based images sometimes don't. The step is conditional and a no-op if wget already exists.

**Integrity checks unchanged from the prior version:**
- size sanity (>100KB)
- PK magic bytes
- Main-Class in manifest
- `chmod 644` for read permission
- SHA1 verification against Nexus's stored sidecar when present

**Endpoint pinned to `analysiscenter.veracode.com`** via `-Dveracode.wrapper.api.host` — the host you've confirmed works.

## Calling pattern (filename-agnostic)

The composite handles versioned filenames automatically. If Nexus serves the wrapper as `vosp-api-wrappers-java-25.4.0.jar` instead of `-with-dependencies.jar`, no input changes:

```yaml
- uses: ./.github/actions/veracode-wrapper-scan
  with:
    scan_mode: sandbox
    artifact_path: build/app.zip
    app_name: my-service
    sandbox_name: ${{ github.ref_name }}
    veracode_api_id: ${{ secrets.VERACODE_API_ID }}
    veracode_api_key: ${{ secrets.VERACODE_API_KEY }}
    nexus_url: https://nexus.corp.example.com
    nexus_user: ${{ secrets.NEXUS_USER }}
    nexus_password: ${{ secrets.NEXUS_PASSWORD }}
    # nexus_jar_path defaults to vosp-api-wrappers-java/latest/...
    # but override if your repo layout differs
```

## A quick check before you ship this

It's worth running this on a runner first and confirming Nexus actually sends `Content-Disposition` for raw repos. If it doesn't, wget falls back to the URL basename, which works but doesn't give you version capture. A one-line test:

```bash
wget --content-disposition --trust-server-names \
     --user="$NEXUS_USER" --password="$NEXUS_PASSWORD" \
     -nv "$URL" 2>&1 | grep -i 'saved'
```

The output `[file:url] -> "actual-filename.jar" [1]` or `Saving to: 'actual-filename.jar'` will show you what name was chosen. If it's the URL basename rather than a versioned name, you'll know Nexus isn't sending the header — not a problem for the composite (it still works), just an FYI that filename preservation in your environment uses URL basename rather than server-supplied name.

If you want, I can also update the Pipeline Scan composite (the zip-extraction one) to use wget the same way — same filename-preservation pattern applied to the zip download.