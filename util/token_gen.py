"""Standalone helper to print a long-lived JWT for local testing."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if REPO_ROOT.as_posix() not in sys.path:
	sys.path.insert(0, REPO_ROOT.as_posix())

from services.auth_service import generate_startup_token


if __name__ == "__main__":
	generate_startup_token()