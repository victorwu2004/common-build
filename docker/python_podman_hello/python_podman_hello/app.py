"""
Simple Hello World Python App
Designed to run in a Docker/Podman container.

Demonstrates:
- Basic Python output
- Reading environment variables (common in containers)
- Simple loop with sleep (shows the container is running)
- Graceful shutdown handling
"""

import os
import sys
import time
import signal
from datetime import datetime

# ─── Read environment variables (passed from container) ────────────────
NAME = os.getenv("NAME", "World")
INTERVAL = int(os.getenv("INTERVAL", "5"))
MESSAGE = os.getenv("MESSAGE", "Hello from Python in a container!")


def signal_handler(sig, frame):
    """Handle Ctrl+C and container stop signals gracefully"""
    print("\n👋 Goodbye! Container shutting down...")
    sys.exit(0)


def main():
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("=" * 60)
    print(f"  🐍 Python Hello World in Container")
    print("=" * 60)
    print(f"  Python version:  {sys.version.split()[0]}")
    print(f"  Container host:  {os.uname().nodename}")
    print(f"  Started at:      {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  Message:         {MESSAGE}")
    print(f"  Greeting for:    {NAME}")
    print(f"  Loop interval:   {INTERVAL} seconds")
    print("=" * 60)
    print()
    
    counter = 0
    while True:
        counter += 1
        now = datetime.now().strftime("%H:%M:%S")
        print(f"[{now}] Hello, {NAME}! (message #{counter})")
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
