"""Start the local workspace with the user's existing FE connection.

Reads the explicitly selected local profile without copying its credential.
Never prints the credential or modifies the source application configuration.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import sys
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def configure_fe(profile: Path, model: str = "gpt-6-astra") -> None:
    if model not in {"gpt-6-astra", "gpt-5.6-sol"}:
        raise ValueError("Choose gpt-6-astra or gpt-5.6-sol")
    data = json.loads(profile.read_text(encoding="utf-8-sig"))
    env = data.get("env", {})
    base = env.get("ANTHROPIC_BASE_URL", "").rstrip("/")
    url = urlsplit(base)
    if (url.scheme != "https" or url.hostname != "api.forceeasyai.com"
            or url.username or url.password or url.query or url.fragment
            or url.path not in {"", "/v1"} or url.port not in {None, 443}):
        raise ValueError("The selected profile must use https://api.forceeasyai.com")
    key = env.get("ANTHROPIC_AUTH_TOKEN") or env.get("ANTHROPIC_API_KEY")
    if not isinstance(key, str) or not key.strip():
        raise ValueError("The selected FE profile has no API key")
    os.environ.update(VTE_BASE_URL="https://api.forceeasyai.com/v1",
                      VTE_API_KEY=key.strip(), VTE_MODEL=model, VTE_API_STYLE="responses",
                      VTE_REASONING_EFFORT="low", VTE_MAX_OUTPUT_TOKENS="6000", VTE_CALL_TIMEOUT="240")
    for role in "ABCD":
        os.environ.pop("VTE_MODEL_" + role, None)


def main() -> int:
    parser = argparse.ArgumentParser(description="VTE Anticoagulation Assistant with FE")
    parser.add_argument("--profile", type=Path, default=Path.home() / ".claude/settings.json")
    parser.add_argument("--model", choices=["gpt-6-astra", "gpt-5.6-sol"], default="gpt-6-astra")
    parser.add_argument("--port", type=int, default=8769)
    parser.add_argument("--open-browser", action="store_true")
    args = parser.parse_args()
    try:
        configure_fe(args.profile, args.model)
    except (OSError, ValueError, TypeError, AttributeError):
        print("FE configuration unavailable: check the selected local profile and FE endpoint.")
        return 1
    from vte_review.server import serve
    return serve(port=args.port, runs_dir=ROOT / "runs", open_browser=args.open_browser)


if __name__ == "__main__":
    raise SystemExit(main())
