"""Launch an agent script with the studio's safe get_ips patch applied before it runs."""

from __future__ import annotations

import runpy
import sys


def _patch_get_ips() -> None:
    """Announce a few real IPv4s only (relay caps 10 endpoints) and never call the blocking ipify API."""
    import ifaddr
    import connectonion.network.announce as _announce

    if getattr(_announce.get_ips, "_co_studio_patched", False):
        return

    def _get_ips() -> list[str]:
        preferred: list[str] = []
        rest: list[str] = []
        for adapter in ifaddr.get_adapters():
            nic = str(adapter.name)
            if any(bad in nic for bad in ("utun", "awdl", "llw", "bridge", "vmnet", "vnic", "vbox", "tap", "tun")):
                continue  # VPN / VM / AirDrop adapters
            for ip in adapter.ips:
                if not isinstance(ip.ip, str):
                    continue  # IPv6 arrives as a tuple — IPv4 only
                if ip.ip.startswith("127.") or ip.ip.startswith("169.254."):
                    continue  # loopback dupe / link-local junk
                (preferred if nic in ("en0", "en1") else rest).append(ip.ip)
        seen: set[str] = set()
        ips = [ip for ip in ["localhost", *preferred, *rest] if not (ip in seen or seen.add(ip))][:4]
        print(f"[co-studio] announce ips={','.join(ips)} endpoints={2 * len(ips)}", flush=True)
        return ips

    _get_ips._co_studio_patched = True  # type: ignore[attr-defined]
    _announce.get_ips = _get_ips


def main() -> None:
    """Patch announce.get_ips, then run the agent script as __main__ in this process."""
    if len(sys.argv) != 2:
        sys.exit("usage: co_studio_runner.py <agent.py>")
    try:
        _patch_get_ips()
    except Exception as exc:  # noqa: BLE001 — a framework refactor must not block launch
        print(f"[co-studio] get_ips patch failed: {exc!r}", flush=True)
    runpy.run_path(sys.argv[1], run_name="__main__")


if __name__ == "__main__":
    main()
