"""CLI Launcher for the FCA-IGAR Research Console Web Interface.

Starts a local FastAPI server hosting the interactive demonstration and
official research results dashboard.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import uvicorn


def main():
    parser = argparse.ArgumentParser(
        description="FCA-IGAR Research Console and Demonstration Web Interface"
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host address to bind the server to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)"
    )
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload for development"
    )

    args = parser.parse_args()

    print("======================================================================")
    print("      FCA-IGAR Research Console & Interactive Demonstration           ")
    print("      Failure-Conditioned Authorization with IGAR (Spec v0.3.9)       ")
    print("======================================================================")
    print(f"Server starting at: http://{args.host}:{args.port}")
    print("Press Ctrl+C to terminate the server.\n")

    uvicorn.run(
        "web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
