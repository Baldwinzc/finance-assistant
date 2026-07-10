from __future__ import annotations

from pathlib import Path


def load_private_env() -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    cwd = Path.cwd()
    load_dotenv(cwd / ".env.local", override=False)
    load_dotenv(cwd / ".env", override=False)
