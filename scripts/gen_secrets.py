#!/usr/bin/env python3
"""Fill LABD_BRAIN_SECRET / LABD_PAIRING_SECRET in .env if missing. Idempotent."""
import re
import secrets
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
NEEDED = ["LABD_BRAIN_SECRET", "LABD_PAIRING_SECRET"]


def main() -> None:
    if not ENV_PATH.exists():
        print(f"no .env at {ENV_PATH}, run `just init` first (copies .env.example)")
        return
    text = ENV_PATH.read_text()
    lines = text.splitlines()
    present = {line.split("=", 1)[0] for line in lines if "=" in line and not line.startswith("#")}
    changed = False
    for key in NEEDED:
        has_value = any(
            line.startswith(f"{key}=") and line.split("=", 1)[1].strip()
            for line in lines
        )
        if has_value:
            continue
        value = secrets.token_hex(32)
        if key in present:
            lines = [
                f"{key}={value}" if line.startswith(f"{key}=") else line
                for line in lines
            ]
        else:
            lines.append(f"{key}={value}")
        changed = True
        print(f"generated {key}")
    if changed:
        ENV_PATH.write_text("\n".join(lines) + "\n")
    else:
        print("secrets already present, nothing to do")


if __name__ == "__main__":
    main()
