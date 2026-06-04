#!/usr/bin/env python3
import argparse
import warnings
from pathlib import Path

from smoke_phase3 import run_smoke


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compatibility wrapper for legacy phase-2 smoke command")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    return parser.parse_args()


def main() -> None:
    warnings.warn(
        "smoke_phase2.py is now a compatibility wrapper. Use smoke_phase3.py for northbound/southbound-separated checks.",
        DeprecationWarning,
        stacklevel=2,
    )
    args = parse_args()
    run_smoke(host=args.host, port=args.port, project_root=Path(__file__).resolve().parents[1])


if __name__ == "__main__":
    main()
