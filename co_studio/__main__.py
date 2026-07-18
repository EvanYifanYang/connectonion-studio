"""Entry point: serve on 127.0.0.1:9900 and open the dashboard in the browser."""

from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import webbrowser

import uvicorn

from . import config
from .app import create_app

def _print_banner(url: str) -> None:
    """A concise, Jupyter-style startup line pointing at the dashboard URL."""
    tty = sys.stdout.isatty() and not os.environ.get("NO_COLOR")
    bold = "\033[1m" if tty else ""
    dim = "\033[2m" if tty else ""
    reset = "\033[0m" if tty else ""
    print(f"\n  {bold}ConnectOnion Studio{reset}  →  {url}   {dim}(Ctrl+C to stop){reset}\n", flush=True)


def main(argv: list[str] | None = None) -> None:
    """Start the loopback-only studio server; pop the dashboard unless --no-browser."""
    parser = argparse.ArgumentParser(prog="co-studio", description="ConnectOnion Studio — local agent test cockpit.")
    parser.add_argument("--no-browser", action="store_true", help="do not open the dashboard in a browser (headless/CI)")
    args = parser.parse_args(argv)
    url = f"http://{config.STUDIO_HOST}:{config.STUDIO_PORT}"
    _print_banner(url)
    if not args.no_browser:
        threading.Timer(1.2, webbrowser.open, args=(url,)).start()
    # access_log=False silences uvicorn's per-request spam (every /css, /js, /assets 304 and
    # WebSocket accept); the startup / doctor / shutdown lines stay. timeout_graceful_shutdown
    # stops it waiting forever for a lingering browser WebSocket so Ctrl+C / close exits promptly.
    server = uvicorn.Server(uvicorn.Config(
        create_app(), host=config.STUDIO_HOST, port=config.STUDIO_PORT,
        log_level="info", access_log=False, timeout_graceful_shutdown=5,
    ))
    # Closing the terminal (SIGHUP) should stop the studio cleanly, not leave an orphan that
    # lingers, serves nothing, and blocks the port on the next launch. uvicorn only handles
    # SIGINT/SIGTERM, so map SIGHUP onto its graceful-exit flag.
    if hasattr(signal, "SIGHUP"):
        signal.signal(signal.SIGHUP, lambda *_: setattr(server, "should_exit", True))
    server.run()


if __name__ == "__main__":
    main()
