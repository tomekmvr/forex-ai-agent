from __future__ import annotations

import os

from src.admin.run_http import main as run_http_main


def main() -> int:
    os.environ.setdefault("FOREX_AGENT_ADMIN_SOURCE_MODE", "demo")
    os.environ.setdefault("FOREX_AGENT_ADMIN_EXECUTION_MODE", "paper")
    return run_http_main()


if __name__ == "__main__":
    raise SystemExit(main())