#!/usr/bin/env python3
"""Install the Mise memory provider into a Hermes profile."""

from __future__ import annotations

import argparse
import os
import shutil
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="Install Mise into $HERMES_HOME/plugins/mise")
    parser.add_argument("--hermes-home", type=Path, default=Path(os.environ.get("HERMES_HOME", "~/.hermes")).expanduser())
    parser.add_argument("--force", action="store_true", help="replace an existing Mise plugin directory")
    args = parser.parse_args()

    source = Path(__file__).resolve().parents[1] / "hermes-plugin" / "mise"
    destination = args.hermes_home.resolve() / "plugins" / "mise"
    required = {"__init__.py", "plugin.yaml", "client.py", "retrieval.py"}
    missing = sorted(name for name in required if not (source / name).is_file())
    if missing:
        parser.error("source tree is incomplete: " + ", ".join(missing))

    if destination.exists():
        if not args.force:
            parser.error(f"{destination} already exists; pass --force to replace it")
        shutil.rmtree(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(source, destination, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))

    installed_missing = sorted(name for name in required if not (destination / name).is_file())
    if installed_missing:
        raise RuntimeError("install verification failed: " + ", ".join(installed_missing))
    print(destination)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
