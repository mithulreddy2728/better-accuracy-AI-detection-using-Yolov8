#!/usr/bin/env python3
"""
AI Engine Entry Point
Connects to the backend and polls for cameras to process.
"""

import os
import sys
import time
import logging

# Ensure the project root (/app) is in sys.path so that
# 'from ai_engine.xyz import ...' resolves correctly inside the container.
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from ai_engine.backend_integration import BackendIntegration

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger(__name__)


def wait_for_backend(api_url: str, retries: int = 20, delay: int = 5) -> bool:
    """Poll the backend health endpoint until it's ready."""
    import requests

    for attempt in range(1, retries + 1):
        try:
            response = requests.get(f"{api_url}/", timeout=5)
            if response.status_code == 200:
                logger.info("✓ Backend is ready at %s", api_url)
                return True
        except Exception:
            pass
        logger.info(
            "⏳ Waiting for backend… attempt %d/%d (retry in %ds)",
            attempt,
            retries,
            delay,
        )
        time.sleep(delay)
    logger.error("✗ Backend did not become ready after %d attempts", retries)
    return False


def main():
    api_url = os.getenv("AI_API_BASE_URL", "http://localhost:8000")
    detection_interval = int(os.getenv("DETECTION_INTERVAL", "5"))

    logger.info("=== AI Engine Starting ===")
    logger.info("Backend URL : %s", api_url)
    logger.info("Poll interval: %ds", detection_interval)

    # Wait for the backend to be available before attempting login
    if not wait_for_backend(api_url):
        sys.exit(1)

    # Initialise backend integration (performs login internally)
    backend = BackendIntegration(api_base_url=api_url)

    logger.info("✓ AI Engine running. Press Ctrl+C to stop.")

    try:
        while True:
            # The detection logic is triggered from the backend via the
            # live_feed router (streaming endpoint).  The AI engine's role
            # here is to stay alive and handle any async tasks delegated
            # by the backend (e.g. uploading detection results).
            time.sleep(detection_interval)
    except KeyboardInterrupt:
        logger.info("AI Engine stopped by user.")


if __name__ == "__main__":
    main()
