# GitHub Actions Reusable Workflows

A comprehensive collection of reusable GitHub Actions workflows for multi-tech-stack CI/CD pipelines with integrated security scanning (Veracode, Nexus IQ) and artifact management (Nexus Repository).

**All workflows are designed to be called from other repositories**, enabling centralized pipeline management across your organization.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    CENTRAL WORKFLOWS REPOSITORY                             │
│                    (your-org/shared-workflows)                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  BUILD WORKFLOWS         SECURITY WORKFLOWS       PUBLISH WORKFLOWS         │
│  ┌────────────────┐      ┌────────────────┐      ┌────────────────┐        │
│  │ build-dotnet   │      │ scan-veracode  │      │ publish-nexus  │        │
│  │ build-java     │      │ scan-nexus-iq  │      │ (maven/npm/    │        │
│  │ build-nodejs   │      │                │      │  pypi/nuget)   │        │
│  │ build-python   │      │                │      │                │        │
│  └────────────────┘      └────────────────┘      └────────────────┘        │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                                    │
                    Called by application repositories
                                    │
                                    ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                      APPLICATION REPOSITORY                                 │
│                      (your-org/my-app)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  .github/workflows/ci-cd.yml                                                │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │  jobs:                                                               │   │
│  │    build:                                                            │   │
│  │      uses: your-org/shared-workflows/.github/workflows/build-X.yml   │   │
│  │    scan:                                                             │   │
│  │      uses: your-org/shared-workflows/.github/workflows/scan-X.yml    │   │
│  │    publish:                                                          │   │
│  │      uses: your-org/shared-workflows/.github/workflows/publish-X.yml │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Quick Start

### 1. Create Central Workflows Repository

Create a repository to host the shared workflows (e.g., `your-org/shared-workflows`):

```
shared-workflows/
└── .github/
    └── workflows/
        ├── build-dotnet.yml
        ├── build-java.yml
        ├── build-nodejs.yml
        ├── build-python.yml
        ├── scan-veracode.yml
        ├── scan-nexus-iq.yml
        └── publish-nexus.yml
```

### 2. Configure Repository Access

For **public** central repository: No additional configuration needed.

For **private** central repository:
- Go to the central repository Settings → Actions → General
- Under "Access", select "Accessible from repositories in the organization"

### 3. Configure Secrets

Add secrets at the **organization level** (recommended) or in each application repository:

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

### 4. Use in Application Repository

Create a workflow in your application repository that calls the shared workflows:

```yaml
# .github/workflows/ci-cd.yml
name: CI/CD Pipeline

on:
  push:
    branches: [main]

jobs:
  build:
    uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@main
    with:
      project-path: './src/MyApp/MyApp.csproj'
      artifact-name: 'my-app'
    secrets:
      NUGET_AUTH_TOKEN: ${{ secrets.NUGET_AUTH_TOKEN }}

  scan:
    needs: build
    uses: your-org/shared-workflows/.github/workflows/scan-nexus-iq.yml@main
    with:
      artifact-name: 'my-app'
      application-id: 'my-app'
    secrets:
      NEXUS_IQ_URL: ${{ secrets.NEXUS_IQ_URL }}
      NEXUS_IQ_USERNAME: ${{ secrets.NEXUS_IQ_USERNAME }}
      NEXUS_IQ_PASSWORD: ${{ secrets.NEXUS_IQ_PASSWORD }}

  publish:
    needs: [build, scan]
    uses: your-org/shared-workflows/.github/workflows/publish-nexus.yml@main
    with:
      artifact-name: 'my-app'
      repository-format: 'nuget'
      repository-name: 'nuget-releases'
      artifact-id: 'my-app'
      version: ${{ needs.build.outputs.version }}
    secrets:
      NEXUS_URL: ${{ secrets.NEXUS_URL }}
      NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
      NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
```

---

## Workflow Reference

### build-dotnet.yml

Builds .NET applications with full NuGet support.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@main
with:
  project-path: './src/MyApp/MyApp.csproj'
  artifact-name: 'my-app'
  create-nuget-package: true
secrets:
  NUGET_AUTH_TOKEN: ${{ secrets.NUGET_AUTH_TOKEN }}
```

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `dotnet-version` | No | `8.0.x` | .NET SDK version |
| `project-path` | Yes | - | Path to project/solution file |
| `configuration` | No | `Release` | Build configuration |
| `artifact-name` | Yes | - | Name for build artifact |
| `run-tests` | No | `true` | Run unit tests |
| `test-project-path` | No | `**/*Tests.csproj` | Test project path |
| `nuget-source-url` | No | - | Private NuGet feed URL |
| `nuget-config-path` | No | - | Path to NuGet.config |
| `create-nuget-package` | No | `false` | Create NuGet package |
| `nuget-package-id` | No | - | Custom package ID |
| `nuget-include-symbols` | No | `true` | Include symbols package |

**Outputs:**

| Output | Description |
|--------|-------------|
| `artifact-name` | Name of the uploaded artifact |
| `version` | Generated version string |
| `nuget-artifact-name` | Name of the NuGet package artifact |

---

### build-java.yml

Builds Java applications with Maven or Gradle.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/build-java.yml@main
with:
  build-tool: 'maven'
  artifact-name: 'my-java-app'
```

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

**Outputs:**

| Output | Description |
|--------|-------------|
| `artifact-name` | Name of the uploaded artifact |
| `version` | Generated version string |

---

### build-nodejs.yml

Builds Node.js applications with npm, yarn, or pnpm.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/build-nodejs.yml@main
with:
  package-manager: 'npm'
  artifact-name: 'my-nodejs-app'
```

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

Builds Python applications with pip, poetry, or pipenv.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/build-python.yml@main
with:
  package-manager: 'pip'
  artifact-name: 'my-python-app'
```

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `python-version` | No | `3.11` | Python version |
| `package-manager` | No | `pip` | Package manager (pip/poetry/pipenv) |
| `artifact-name` | Yes | - | Name for build artifact |
| `run-tests` | No | `true` | Run unit tests |
| `build-wheel` | No | `true` | Build wheel distribution |
| `requirements-file` | No | `requirements.txt` | Requirements file path |

---

### scan-veracode.yml

Performs Veracode SAST scanning.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/scan-veracode.yml@main
with:
  artifact-name: 'my-app'
  application-name: 'my-application'
  scan-type: 'policy'
secrets:
  VERACODE_API_ID: ${{ secrets.VERACODE_API_ID }}
  VERACODE_API_KEY: ${{ secrets.VERACODE_API_KEY }}
```

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `artifact-name` | Yes | - | Name of artifact to scan |
| `application-name` | Yes | - | Veracode application name |
| `scan-type` | No | `policy` | Scan type (policy/sandbox/sca) |
| `sandbox-name` | No | - | Sandbox name for sandbox scans |
| `fail-on-severity` | No | `High` | Minimum severity to fail |
| `timeout-minutes` | No | `60` | Scan timeout |

**Outputs:**

| Output | Description |
|--------|-------------|
| `scan-status` | Scan completion status |
| `policy-passed` | Whether scan passed policy |

---

### scan-nexus-iq.yml

Performs Nexus IQ SCA scanning.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/scan-nexus-iq.yml@main
with:
  artifact-name: 'my-app'
  application-id: 'my-application'
secrets:
  NEXUS_IQ_URL: ${{ secrets.NEXUS_IQ_URL }}
  NEXUS_IQ_USERNAME: ${{ secrets.NEXUS_IQ_USERNAME }}
  NEXUS_IQ_PASSWORD: ${{ secrets.NEXUS_IQ_PASSWORD }}
```

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `artifact-name` | Yes | - | Name of artifact to scan |
| `application-id` | Yes | - | Nexus IQ application ID |
| `stage` | No | `build` | Scan stage |
| `fail-on-policy-warnings` | No | `false` | Fail on policy warnings |
| `scan-targets` | No | (see workflow) | Targets to scan |

**Outputs:**

| Output | Description |
|--------|-------------|
| `scan-status` | Scan completion status |
| `policy-action` | Policy action (None/Warn/Fail) |
| `report-url` | URL to scan report |

---

### publish-nexus.yml

Publishes artifacts to Nexus Repository.

**Usage:**
```yaml
uses: your-org/shared-workflows/.github/workflows/publish-nexus.yml@main
with:
  artifact-name: 'my-app'
  repository-format: 'nuget'
  repository-name: 'nuget-releases'
  artifact-id: 'my-app'
  version: '1.0.0'
secrets:
  NEXUS_URL: ${{ secrets.NEXUS_URL }}
  NEXUS_USERNAME: ${{ secrets.NEXUS_USERNAME }}
  NEXUS_PASSWORD: ${{ secrets.NEXUS_PASSWORD }}
```

**Inputs:**

| Input | Required | Default | Description |
|-------|----------|---------|-------------|
| `artifact-name` | Yes | - | Name of artifact to publish |
| `repository-format` | Yes | - | Format (maven/npm/pypi/nuget/raw) |
| `repository-name` | Yes | - | Target repository name |
| `group-id` | No | - | Group ID / npm scope |
| `artifact-id` | Yes | - | Artifact ID / package name |
| `version` | Yes | - | Version to publish |
| `classifier` | No | - | Maven classifier |
| `extension` | No | - | File extension |
| `generate-pom` | No | `true` | Generate POM for Maven |

**Outputs:**

| Output | Description |
|--------|-------------|
| `published-url` | URL of published artifact |
| `publish-status` | Publication status |

---

## Best Practices

### Version Pinning

Pin workflows to a specific version or commit for stability:

```yaml
# Pin to a tag (recommended)
uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@v1.0.0

# Pin to a commit SHA (most secure)
uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@a1b2c3d4

# Use latest from main (for development)
uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@main
```

### Branch-Based Configuration

Use conditional logic for environment-specific settings:

```yaml
jobs:
  build:
    uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@main
    with:
      configuration: ${{ github.ref == 'refs/heads/main' && 'Release' || 'Debug' }}

  scan:
    uses: your-org/shared-workflows/.github/workflows/scan-veracode.yml@main
    with:
      scan-type: ${{ github.ref == 'refs/heads/main' && 'policy' || 'sandbox' }}

  publish:
    uses: your-org/shared-workflows/.github/workflows/publish-nexus.yml@main
    with:
      repository-name: ${{ github.ref == 'refs/heads/main' && 'releases' || 'snapshots' }}
```

### Parallel Security Scans

Run multiple scans in parallel to save time:

```yaml
jobs:
  build:
    uses: your-org/shared-workflows/.github/workflows/build-java.yml@main

  veracode-scan:
    needs: build
    uses: your-org/shared-workflows/.github/workflows/scan-veracode.yml@main

  nexus-iq-scan:
    needs: build
    uses: your-org/shared-workflows/.github/workflows/scan-nexus-iq.yml@main

  publish:
    needs: [build, veracode-scan, nexus-iq-scan]  # Waits for both scans
    uses: your-org/shared-workflows/.github/workflows/publish-nexus.yml@main
```

### Passing Outputs Between Jobs

Access outputs from called workflows:

```yaml
jobs:
  build:
    uses: your-org/shared-workflows/.github/workflows/build-dotnet.yml@main
    with:
      artifact-name: 'my-app'

  publish:
    needs: build
    uses: your-org/shared-workflows/.github/workflows/publish-nexus.yml@main
    with:
      version: ${{ needs.build.outputs.version }}
      artifact-name: ${{ needs.build.outputs.artifact-name }}
```

---

## Example Pipelines

Complete example pipelines are provided in the `examples/` directory:

- `dotnet-pipeline.yml` - .NET with NuGet packaging
- `java-pipeline.yml` - Java with Maven
- `nodejs-pipeline.yml` - Node.js with npm
- `python-pipeline.yml` - Python with pip

---

## Troubleshooting

### Common Issues

1. **"Workflow not found"**: Ensure the central repository is accessible and the path is correct.

2. **"Resource not accessible by integration"**: For private repos, enable "Accessible from repositories in the organization" in the central repo settings.

3. **Secret not available**: Use `secrets: inherit` or explicitly pass secrets to called workflows.

4. **Artifact not found**: Ensure `artifact-name` matches between build and subsequent jobs.

### Debug Mode

Enable debug logging:

```yaml
env:
  ACTIONS_STEP_DEBUG: true
```

Or set repository secret `ACTIONS_STEP_DEBUG` = `true`

---

## Directory Structure

```
shared-workflows/
├── .github/
│   └── workflows/
│       ├── build-dotnet.yml      # .NET build workflow
│       ├── build-java.yml        # Java build workflow
│       ├── build-nodejs.yml      # Node.js build workflow
│       ├── build-python.yml      # Python build workflow
│       ├── scan-veracode.yml     # Veracode SAST scanning
│       ├── scan-nexus-iq.yml     # Nexus IQ SCA scanning
│       └── publish-nexus.yml     # Nexus Repository publishing
├── examples/
│   ├── dotnet-pipeline.yml       # Example .NET pipeline
│   ├── java-pipeline.yml         # Example Java pipeline
│   ├── nodejs-pipeline.yml       # Example Node.js pipeline
│   └── python-pipeline.yml       # Example Python pipeline
└── README.md
```

---

## License

MIT License - See LICENSE file for details.
