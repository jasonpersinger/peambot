#!/usr/bin/env python3
"""Substitute .env values into data/.config.yaml.template → data/.config.yaml."""
import re
import sys
from pathlib import Path

ROOT = Path(__file__).parent.parent


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, _, val = line.partition("=")
            env[key.strip()] = val.strip()
    return env


def main() -> None:
    env_path = ROOT / ".env"
    if not env_path.exists():
        print(f"ERROR: {env_path} not found. Copy .env.example and fill in values.", file=sys.stderr)
        sys.exit(1)

    env = load_env(env_path)
    template = (ROOT / "data" / ".config.yaml.template").read_text()

    for key, val in env.items():
        template = template.replace(f"${{{key}}}", val)

    remaining = re.findall(r"\$\{[A-Z_]+\}", template)
    if remaining:
        print(f"WARNING: unfilled placeholders: {', '.join(sorted(set(remaining)))}", file=sys.stderr)

    out = ROOT / "data" / ".config.yaml"
    out.write_text(template)
    print(f"Generated {out}")


if __name__ == "__main__":
    main()
