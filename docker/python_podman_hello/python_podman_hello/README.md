# Python Hello World in Podman

A minimal Python containerized app to learn Docker/Podman basics.

## What This Teaches

- Writing a `Dockerfile` for Python apps
- Building container images with Podman
- Running containers with environment variables
- Container lifecycle (build → run → stop → remove)
- Best practices: layer caching, non-root user, `.dockerignore`

## Prerequisites

### Install Podman

**Fedora/RHEL/CentOS:**
```bash
sudo dnf install podman
```

**Ubuntu/Debian:**
```bash
sudo apt install podman
```

**macOS:**
```bash
brew install podman
podman machine init
podman machine start
```

**Windows:**
- Download from https://podman.io/getting-started/installation
- Or use WSL2: install Podman inside your WSL Linux

### Verify Installation

```bash
podman --version
# Should print: podman version 4.x or higher
```

## Quick Start (One Command)

```bash
# Linux/Mac
./run.sh

# Windows
run.bat
```

This will:
1. Build the container image
2. Clean up old containers
3. Run the app with custom environment variables

## Manual Step-by-Step

### Step 1: Build the Image

```bash
podman build -t python-hello .
```

Output:
```
STEP 1/9: FROM python:3.12-slim
STEP 2/9: LABEL maintainer="you@example.com"
...
Successfully tagged localhost/python-hello:latest
```

### Step 2: Run the Container

```bash
# Basic run
podman run --rm python-hello

# With custom environment variables
podman run --rm \
  -e NAME="Alice" \
  -e INTERVAL="2" \
  -e MESSAGE="Hi from container!" \
  python-hello

# Run in background (detached)
podman run -d --name my-hello python-hello

# View logs of background container
podman logs -f my-hello

# Stop background container
podman stop my-hello
podman rm my-hello
```

## Expected Output

```
============================================================
  🐍 Python Hello World in Container
============================================================
  Python version:  3.12.3
  Container host:  abc123def456
  Started at:      2026-07-04 10:30:15
  Message:         Running in Podman rootless container!
  Greeting for:    Podman User
  Loop interval:   3 seconds
============================================================

[10:30:15] Hello, Podman User! (message #1)
[10:30:18] Hello, Podman User! (message #2)
[10:30:21] Hello, Podman User! (message #3)
```

Press **Ctrl+C** to stop.

## Common Podman Commands

### Image Management

```bash
# List images
podman images

# Remove image
podman rmi python-hello

# Inspect image details
podman inspect python-hello
```

### Container Management

```bash
# List running containers
podman ps

# List all containers (including stopped)
podman ps -a

# Stop a container
podman stop hello-container

# Remove a container
podman rm hello-container

# View logs
podman logs hello-container

# Follow logs in real-time
podman logs -f hello-container

# Execute command inside running container
podman exec -it hello-container /bin/bash
```

### Cleanup

```bash
# Remove all stopped containers
podman container prune

# Remove all unused images
podman image prune

# Nuclear option: remove everything
podman system prune -a
```

## Using podman-compose

If you have `podman-compose` installed:

```bash
# Install if needed
pip install podman-compose

# Start
podman-compose up

# Start in background
podman-compose up -d

# View logs
podman-compose logs -f

# Stop
podman-compose down
```

## Docker Compatibility

**This entire project works with Docker too!** Just replace `podman` with `docker`:

```bash
docker build -t python-hello .
docker run --rm python-hello
```

Podman is a drop-in replacement for Docker with:
- No daemon required (more secure)
- Rootless by default
- Compatible with all Docker commands
- Uses same Dockerfile format

## Understanding the Dockerfile

```dockerfile
FROM python:3.12-slim       # Base image (small, official)
WORKDIR /app                # Working directory inside container
COPY requirements.txt .     # Copy deps first (caching!)
RUN pip install ...         # Install dependencies
COPY app.py .              # Copy application code
USER appuser               # Run as non-root (security)
ENV NAME="World"           # Default environment variable
CMD ["python", "app.py"]   # Command to run
```

### Why This Order?

Docker/Podman caches each `RUN`, `COPY`, `ADD` step. If you change `app.py` but not `requirements.txt`, only steps after `COPY app.py` re-run. **Copying requirements first = faster rebuilds!**

## Customization Examples

### Add a Python Package

Edit `requirements.txt`:
```
requests>=2.31.0
```

Rebuild:
```bash
podman build -t python-hello .
```

### Change the App

Edit `app.py` and rebuild:
```bash
podman build -t python-hello .
podman run --rm python-hello
```

### Different Port for Web Server

If you upgrade this to a Flask app:
```bash
podman run --rm -p 5000:5000 python-hello
```

## File Structure

```
python_podman_hello/
├── app.py                  # Python application
├── Dockerfile              # Container image definition
├── requirements.txt        # Python dependencies
├── .dockerignore           # Files to exclude from image
├── podman-compose.yml      # Compose file (optional)
├── run.sh                  # Linux/Mac quick-start
├── run.bat                 # Windows quick-start
└── README.md               # This file
```

## Troubleshooting

### "Cannot connect to Podman daemon"

Podman doesn't use a daemon! If you see this error, you might be trying to use Podman as Docker's drop-in in an app that requires a socket:

```bash
# Start Podman socket (macOS/Windows)
podman machine start

# Linux: enable socket
systemctl --user start podman.socket
```

### "Permission denied" on run.sh

```bash
chmod +x run.sh
```

### Image too large

Check size:
```bash
podman images python-hello
```

Reduce it by using an even smaller base:
```dockerfile
FROM python:3.12-alpine  # ~50MB instead of ~130MB
```

### Container exits immediately

Check logs:
```bash
podman logs hello-container
```

## Next Steps

Once this works, try:

1. **Add a web server** — Flask/FastAPI in the container
2. **Persist data** — Use volumes to save files
3. **Multi-container** — Add Postgres/Redis via podman-compose
4. **Publish image** — Push to Docker Hub or quay.io

## Resources

- Podman docs: https://docs.podman.io
- Docker docs: https://docs.docker.com
- Python Docker best practices: https://pythonspeed.com/docker/
- Podman vs Docker: https://podman.io/whatis.html

## License

MIT - Use freely for learning.
