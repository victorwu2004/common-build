#!/bin/bash
# Build and run the Python container with Podman

set -e

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

IMAGE_NAME="python-hello"
CONTAINER_NAME="hello-container"

echo ""
echo -e "${CYAN}╔════════════════════════════════════════════════════════════╗${NC}"
echo -e "${CYAN}║   Python Hello World in Podman                            ║${NC}"
echo -e "${CYAN}╚════════════════════════════════════════════════════════════╝${NC}"
echo ""

# Check if podman is installed
if ! command -v podman &> /dev/null; then
    echo -e "${RED}ERROR: Podman not installed${NC}"
    echo "Install Podman:"
    echo "  Fedora/RHEL:  sudo dnf install podman"
    echo "  Ubuntu:       sudo apt install podman"
    echo "  macOS:        brew install podman"
    echo "  Windows:      https://podman.io/getting-started/installation"
    exit 1
fi

echo -e "${GREEN}✓ Podman found: $(podman --version)${NC}"
echo ""

# Step 1: Build the image
echo -e "${YELLOW}[1/3] Building container image...${NC}"
podman build -t $IMAGE_NAME .
echo -e "${GREEN}✓ Image built: $IMAGE_NAME${NC}"
echo ""

# Step 2: Stop and remove old container if exists
echo -e "${YELLOW}[2/3] Cleaning up old containers...${NC}"
podman stop $CONTAINER_NAME 2>/dev/null || true
podman rm $CONTAINER_NAME 2>/dev/null || true
echo -e "${GREEN}✓ Cleanup complete${NC}"
echo ""

# Step 3: Run the container
echo -e "${YELLOW}[3/3] Running container...${NC}"
echo -e "${CYAN}(Press Ctrl+C to stop)${NC}"
echo ""

podman run \
    --name $CONTAINER_NAME \
    --rm \
    -e NAME="Podman User" \
    -e INTERVAL="3" \
    -e MESSAGE="Running in Podman rootless container!" \
    $IMAGE_NAME
