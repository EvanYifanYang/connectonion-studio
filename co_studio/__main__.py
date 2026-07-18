"""Entry point: serve on 127.0.0.1:9900 and open the dashboard in the browser."""

from __future__ import annotations

import argparse
import threading
import webbrowser

import uvicorn

from . import config
from .app import create_app


def main(argv: list[str] | None = None) -> None:
    """Start the loopback-only studio server; pop the dashboard unless --no-browser."""
    parser = argparse.ArgumentParser(prog="co-studio", description="ConnectOnion Studio — local agent test cockpit.")
    parser.add_argument("--no-browser", action="store_true", help="do not open the dashboard in a browser (headless/CI)")
    args = parser.parse_args(argv)
    url = f"http://{config.STUDIO_HOST}:{config.STUDIO_PORT}"
    if not args.no_browser:
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    uvicorn.run(create_app(), host=config.STUDIO_HOST, port=config.STUDIO_PORT, log_level="info")


if __name__ == "__main__":
    main()
