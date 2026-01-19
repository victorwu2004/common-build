# GitHub Actions Reusable Workflows & Composite Actions

A comprehensive set of reusable GitHub Actions workflows and composite actions for multi-tech-stack CI/CD pipelines with integrated security scanning (Veracode, Nexus IQ) and artifact management (Nexus Repository).

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        CI/CD Pipeline                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────┐                                               │
│  │   BUILD     │  → build-dotnet.yml (with NuGet support)      │
│  │   STAGE     │  → build-java.yml                             │
│  │  (Workflow) │  → build-nodejs.yml                           │
│  │             │  → build-python.yml                           │
│  └──────┬──────┘                                               │
│         │                                                       │
│         ▼                                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │         SECURITY SCAN STAGE             │                   │
│  │  ┌─────────────┐   ┌─────────────────┐  │                   │
│  │  │  Veracode   │   │    Nexus IQ     │  │  (Parallel)       │
│  │  │  (Workflow) │   │    (Action)     │  │                   │
│  │  └─────────────┘   └─────────────────┘  │                   │
│  └──────────────────────┬──────────────────┘                   │
│                         │                                       │
│                         ▼                                       │
│  ┌─────────────────────────────────────────┐                   │
│  │         PUBLISH STAGE                    │                   │
│  │  ┌─────────────────────────────────────┐│                   │
│  │  │   Nexus Publish (Composite Action)  ││                   │
│  │  │  • Maven  • npm  • PyPI  • NuGet    ││                   │
│  │  └─────────────────────────────────────┘│                   │
│  └─────────────────────────────────────────┘                   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

## Components

### Reusable Workflows (`.github/workflows/`)

| Workflow | Tech Stack | Description |
|----------|------------|-------------|
| `build-dotnet.yml` | .NET | Builds .NET apps with NuGet restore, caching, packaging, and tests |
| `build-java.yml` | Java | Builds Java applications with Maven or Gradle |
| `build-nodejs.yml` | Node.js | Builds Node.js applications with npm, yarn, or pnpm |
| `build-python.yml` | Python | Builds Python applications with pip, poetry, or pipenv |
| `scan-veracode.yml` | All | Veracode SAST scanning with policy or sandbox mode |

### Composite Actions (`.github/actions/`)

| Action | Description |
|--------|-------------|
| `nexus-iq-scan` | Nexus IQ SCA/OSS scanning with policy evaluation |
| `nexus-publish` | Publish artifacts to Nexus Repository (Maven, npm, PyPI, NuGet, Raw) |

## Quick Start

### 1. Copy to Your Repository

```
your-repo/
├── .github/
│   ├── actions/
│   │   ├── nexus-iq-scan/
│   │   │   └── action.yml
│   │   └── nexus-publish/
│   │       └── action.yml
│   └── workflows/
│       ├── build-dotnet.yml
│       ├── build-java.yml
│       ├── build-nodejs.yml
│       ├── build-python.yml
│       └── scan-veracode.yml
```

### 2. Configure Repository Secrets

| Secret | Description |
|--------|-------------|
| `VERACODE_API_ID` | Veracode API ID |
| `VERACODE_API_KEY` | Veracode API Key |
| `NEXUS_IQ_URL` | Nexus IQ server URL |
| `NEXUS_IQ_USERNAME` | Nexus IQ username |
| `NEXUS_IQ_PASSWORD` | Nexus IQ password |
| `NEXUS_URL` | Nexus Repository URL |
| `NEXUS_USERNAME` | Nexus Repository username |
| `NEXUS_PASSWORD` | Nexus Repository password |
| `NUGET_AUTH_TOKEN` | (Optional) NuGet feed auth token |

### 3. Create Your Pipeline

```yaml
name: My Application Pipeline

on:
  push:
    branches: [main, develop]

jobs:
  build:
    uses: ./.github/workflows/build-dotnet.yml
    with:
      project-path: './src/MyApp/MyApp.csproj'
      artifact-name: 'my-app-artifact'
      create-nuget-package: true
    secrets:
      NUGET_AUTH_TOKEN: ${{ secrets.NUGET_AUTH_TOKEN }}

  nexus-iq-scan:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: my-app-artifact
          path: ./artifact
      - uses: ./.github/actions/nexus-iq-scan
        with:
          nexus-iq-url: ${{ secrets.NEXUS_IQ_URL }}
          nexus-iq-username: ${{ secrets.NEXUS_IQ_USERNAME }}
          nexus-iq-password: ${{ secrets.NEXUS_IQ_PASSWORD }}
          application-id: 'my-application'
          scan-targets: './artifact'

  publish:
    needs: [build, nexus-iq-scan]
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/download-artifact@v4
        with:
          name: my-app-artifact-nuget
          path: ./nupkg
      - uses: ./.github/actions/nexus-publish
        with:
          nexus-url: ${{ secrets.NEXUS_URL }}
          nexus-username: ${{ secrets.NEXUS_USERNAME }}
          nexus-password: ${{ secrets.NEXUS_PASSWORD }}
          repository-format: 'nuget'
          repository-name: 'nuget-releases'
          artifact-path: './nupkg'
          artifact-id: 'my-app'
          version: ${{ needs.build.outputs.version }}
```

---

## Workflow Reference

### build-dotnet.yml

Enhanced .NET build workflow with full NuGet support.

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `dotnet-version` | No | `8.0.x` | .NET SDK version |
| `project-path` | Yes | - | Path to project/solution file |
| `configuration` | No | `Release` | Build configuration |
| `artifact-name` | Yes | - | Name for build artifact |
| `publish-path` | No | `./publish` | Publish output path |
| `run-tests` | No | `true` | Run unit tests |
| `test-project-path` | No | `**/*Tests.csproj` | Test project path |
| `nuget-source-url` | No | - | Private NuGet feed URL |
| `nuget-config-path` | No | - | Path to NuGet.config |
| `create-nuget-package` | No | `false` | Create NuGet package |
| `nuget-package-id` | No | - | Custom package ID |
| `nuget-include-symbols` | No | `true` | Include symbols package |
| `nuget-include-source` | No | `false` | Include source in symbols |

**Secrets:**

| Secret | Required | Description |
|--------|----------|-------------|
| `NUGET_AUTH_TOKEN` | No | Auth token for private NuGet feeds |

**Outputs:**

| Output | Description |
|--------|-------------|
| `artifact-path` | Path to built artifact |
| `version` | Generated version string |
| `nuget-package-path` | Path to NuGet package(s) |

**Example:**

```yaml
build:
  uses: ./.github/workflows/build-dotnet.yml
  with:
    dotnet-version: '8.0.x'
    project-path: './src/MyApp/MyApp.csproj'
    artifact-name: 'my-app'
    create-nuget-package: true
    nuget-source-url: 'https://nexus.example.com/repository/nuget-group/'
    nuget-include-symbols: true
  secrets:
    NUGET_AUTH_TOKEN: ${{ secrets.NUGET_AUTH_TOKEN }}
```

---

### build-java.yml

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `java-version` | No | `17` | Java version |
| `java-distribution` | No | `temurin` | Java distribution |
| `build-tool` | No | `maven` | Build tool (maven/gradle) |
| `pom-path` | No | `pom.xml` | Path to pom.xml/build.gradle |
| `artifact-name` | Yes | - | Name for build artifact |
| `run-tests` | No | `true` | Run unit tests |
| `maven-goals` | No | `clean package` | Maven goals |
| `gradle-tasks` | No | `clean build` | Gradle tasks |

---

### build-nodejs.yml

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `node-version` | No | `20` | Node.js version |
| `package-manager` | No | `npm` | Package manager (npm/yarn/pnpm) |
| `working-directory` | No | `.` | Working directory |
| `artifact-name` | Yes | - | Name for build artifact |
| `run-tests` | No | `true` | Run unit tests |
| `build-command` | No | - | Custom build command |
| `output-directory` | No | `dist` | Build output directory |

---

### build-python.yml

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `python-version` | No | `3.11` | Python version |
| `package-manager` | No | `pip` | Package manager (pip/poetry/pipenv) |
| `working-directory` | No | `.` | Working directory |
| `artifact-name` | Yes | - | Name for build artifact |
| `run-tests` | No | `true` | Run unit tests |
| `build-wheel` | No | `true` | Build wheel distribution |
| `requirements-file` | No | `requirements.txt` | Requirements file path |

---

## Composite Action Reference

### nexus-iq-scan

Scans artifacts for security vulnerabilities using Sonatype Nexus IQ.

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `nexus-iq-url` | Yes | - | Nexus IQ server URL |
| `nexus-iq-username` | Yes | - | Nexus IQ username |
| `nexus-iq-password` | Yes | - | Nexus IQ password |
| `application-id` | Yes | - | Nexus IQ application ID |
| `scan-targets` | Yes | `.` | Path to files/directories to scan |
| `stage` | No | `build` | Scan stage (develop/build/stage-release/release/operate) |
| `fail-on-policy-warnings` | No | `false` | Fail on policy warnings |
| `result-file` | No | `nexus-iq-results.json` | Path to save results |

**Outputs:**

| Output | Description |
|--------|-------------|
| `scan-status` | Scan status (success/failed/warning) |
| `policy-action` | Policy action result (None/Warn/Fail) |
| `report-url` | URL to the scan report |
| `critical-count` | Number of critical vulnerabilities |
| `severe-count` | Number of severe vulnerabilities |

**Example:**

```yaml
- name: Run Nexus IQ Scan
  uses: ./.github/actions/nexus-iq-scan
  with:
    nexus-iq-url: ${{ secrets.NEXUS_IQ_URL }}
    nexus-iq-username: ${{ secrets.NEXUS_IQ_USERNAME }}
    nexus-iq-password: ${{ secrets.NEXUS_IQ_PASSWORD }}
    application-id: 'my-application'
    scan-targets: './artifact'
    stage: 'build'
    fail-on-policy-warnings: false
```

---

### nexus-publish

Publishes artifacts to Sonatype Nexus Repository Manager.

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `nexus-url` | Yes | - | Nexus Repository URL |
| `nexus-username` | Yes | - | Nexus username |
| `nexus-password` | Yes | - | Nexus password |
| `repository-format` | Yes | - | Format (maven/npm/pypi/nuget/raw) |
| `repository-name` | Yes | - | Target repository name |
| `artifact-path` | Yes | - | Path to artifact(s) |
| `group-id` | No | - | Group ID / Scope |
| `artifact-id` | Yes | - | Artifact ID / Package name |
| `version` | Yes | - | Version to publish |
| `classifier` | No | - | Maven classifier |
| `extension` | No | - | File extension |
| `generate-pom` | No | `true` | Generate POM for Maven |

**Outputs:**

| Output | Description |
|--------|-------------|
| `published-url` | URL of the published artifact |
| `publish-status` | Publication status (success/failed) |

**Example (NuGet):**

```yaml
- name: Publish to Nexus
  uses: ./.github/actions/nexus-publish
  with:
    nexus-url: ${{ secrets.NEXUS_URL }}
    nexus-username: ${{ secrets.NEXUS_USERNAME }}
    nexus-password: ${{ secrets.NEXUS_PASSWORD }}
    repository-format: 'nuget'
    repository-name: 'nuget-releases'
    artifact-path: './nupkg'
    artifact-id: 'MyApp'
    version: '1.0.0'
```

**Example (Maven):**

```yaml
- name: Publish to Nexus
  uses: ./.github/actions/nexus-publish
  with:
    nexus-url: ${{ secrets.NEXUS_URL }}
    nexus-username: ${{ secrets.NEXUS_USERNAME }}
    nexus-password: ${{ secrets.NEXUS_PASSWORD }}
    repository-format: 'maven'
    repository-name: 'maven-releases'
    artifact-path: './target/my-app-1.0.0.jar'
    group-id: 'com.example'
    artifact-id: 'my-app'
    version: '1.0.0'
    extension: 'jar'
```

---

## Best Practices

### Branch-Based Configuration

Use conditional logic for branch-specific behavior:

```yaml
jobs:
  scan:
    uses: ./.github/workflows/scan-veracode.yml
    with:
      scan-type: ${{ github.ref == 'refs/heads/main' && 'policy' || 'sandbox' }}

  publish:
    steps:
      - uses: ./.github/actions/nexus-publish
        with:
          repository-name: ${{ github.ref == 'refs/heads/main' && 'releases' || 'snapshots' }}
```

### Parallel Security Scans

Run Veracode and Nexus IQ scans in parallel:

```yaml
jobs:
  build:
    uses: ./.github/workflows/build-java.yml

  veracode:
    needs: build
    uses: ./.github/workflows/scan-veracode.yml

  nexus-iq:
    needs: build
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/nexus-iq-scan

  publish:
    needs: [build, veracode, nexus-iq]  # Waits for both scans
    runs-on: ubuntu-latest
    steps:
      - uses: ./.github/actions/nexus-publish
```

### Version Management

Access build outputs in subsequent jobs:

```yaml
jobs:
  build:
    uses: ./.github/workflows/build-dotnet.yml

  publish:
    needs: build
    steps:
      - uses: ./.github/actions/nexus-publish
        with:
          version: ${{ needs.build.outputs.version }}
```

---

## Example Pipelines

Complete example pipeline files are provided:

- `example-dotnet-pipeline.yml` - .NET with NuGet packaging
- `example-java-pipeline.yml` - Java with Maven
- `example-nodejs-pipeline.yml` - Node.js with npm
- `example-python-pipeline.yml` - Python with pip

---

## Troubleshooting

### Common Issues

1. **Veracode scan timeout**: Increase `timeout-minutes` input
2. **Nexus IQ scan fails to find dependencies**: Check `scan-targets` path
3. **Publish fails with 401**: Verify Nexus credentials and permissions
4. **Build artifact not found**: Ensure `artifact-name` matches between jobs
5. **NuGet restore fails**: Check `nuget-source-url` and `NUGET_AUTH_TOKEN`

### Debug Mode

Enable debug logging:
```yaml
env:
  ACTIONS_STEP_DEBUG: true
```

Or set repository secret `ACTIONS_STEP_DEBUG` = `true`

---

## License

MIT License - See LICENSE file for details.
