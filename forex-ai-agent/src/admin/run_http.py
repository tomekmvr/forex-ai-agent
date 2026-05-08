from __future__ import annotations

import os
import socket
import subprocess
import sys
from pathlib import Path


def _detect_local_ip() -> str:
    probe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        probe.connect(("8.8.8.8", 80))
        return probe.getsockname()[0]
    except OSError:
        return "127.0.0.1"
    finally:
        probe.close()


def main() -> int:
    host = os.getenv("ADMIN_PANEL_HOST", "0.0.0.0")
    port = os.getenv("ADMIN_PANEL_PORT", "8501")
    app_path = Path(__file__).with_name("app.py")
    local_ip = _detect_local_ip()

    print(f"Starting admin panel over HTTP on http://127.0.0.1:{port}")
    if host == "0.0.0.0":
        print(f"LAN URL: http://{local_ip}:{port}")

    command = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(app_path),
        "--server.headless=true",
        f"--server.address={host}",
        f"--server.port={port}",
    ]
    return subprocess.call(command)


if __name__ == "__main__":
    raise SystemExit(main())
