"""Ed25519 identity and QR helpers around connectonion.address."""

from __future__ import annotations

import io
from pathlib import Path
from urllib.parse import quote

import segno


def create(co_dir: Path) -> str:
    """Generate a fresh identity into <agent_dir>/.co and return its 0x address."""
    from connectonion import address as co_address

    co_dir.mkdir(parents=True, exist_ok=True)
    data = co_address.generate()
    co_address.save(data, co_dir)
    return str(data["address"])


def load_address(co_dir: Path) -> str | None:
    """Read the 0x address saved in a .co directory, if present."""
    from connectonion import address as co_address

    data = co_address.load(co_dir)
    return str(data["address"]) if data else None


def lan_ip() -> str | None:
    """Best-guess LAN IPv4 (physical NIC; skips loopback/link-local/VPN/VM) for the direct QR endpoint."""
    try:
        import ifaddr
    except ImportError:
        return None
    skip = ("utun", "awdl", "llw", "bridge", "vmnet", "vnic", "vbox", "tap", "tun",
            "vethernet", "hyper-v", "vmware", "virtualbox", "loopback", "npcap", "wsl",
            "veth", "docker", "br-", "virbr")
    prefer = ("en0", "en1", "eth", "wlan", "wi-fi", "wifi", "ethernet")
    preferred: list[str] = []
    rest: list[str] = []
    for adapter in ifaddr.get_adapters():
        label = f"{getattr(adapter, 'nice_name', '') or ''} {adapter.name}".lower()
        if any(bad in label for bad in skip):
            continue
        is_preferred = any(good in label for good in prefer)
        for ip in adapter.ips:
            if not isinstance(ip.ip, str):
                continue  # IPv6 arrives as a tuple
            if ip.ip.startswith("127.") or ip.ip.startswith("169.254."):
                continue
            (preferred if is_preferred else rest).append(ip.ip)
    picks = preferred or rest
    return picks[0] if picks else None


def add_agent_qr_payload(address: str, name: str | None = None, port: int | None = None) -> str:
    """The iOS "Add Agent" deep link: connectonion://add?address=…&name=…&endpoint=…

    A single scan fills the agent's address, name, and DIRECT LAN endpoint (so the phone connects
    straight to the agent, bypassing the relay). name/endpoint are percent-encoded and optional;
    the endpoint is omitted when no LAN IP is available. See docs/connectonion-qr-protocol.md.
    """
    parts = [f"address={address}"]
    if name:
        parts.append(f"name={quote(name, safe='')}")
    if port:
        ip = lan_ip()
        if ip:
            parts.append(f"endpoint={quote(f'http://{ip}:{port}', safe='')}")
    return "connectonion://add?" + "&".join(parts)


def qr_svg(payload: str) -> str:
    """Render a payload string as a high-error-correction SVG QR on a white card."""
    qr = segno.make(payload, error="h")
    buffer = io.BytesIO()
    qr.save(buffer, kind="svg", scale=8, border=3, dark="#262523", light="#FFFFFF", xmldecl=True)
    return buffer.getvalue().decode("utf-8")
