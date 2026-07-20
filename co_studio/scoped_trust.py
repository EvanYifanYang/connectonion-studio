"""Studio-owned, per-agent trust storage for ConnectOnion 1.2.1.

ConnectOnion 1.2.1 accepts a ``TrustAgent`` instance, but its built-in instance
stores contacts, allowlists, blocklists, and admins in the user's global
``~/.co`` directory.  Studio runs multiple independent agents, so sharing that
state lets onboarding with one agent silently authorize the same client for all
other agents.

This adapter keeps the framework protocol and policy parsing while overriding
every trust-state operation to use the agent's explicit ``co_dir``.  It is
injected by Studio's runner, leaving both the company package and generated
standalone agent files unchanged.
"""

from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any, Callable

from connectonion.network.trust.trust_agent import Decision, TrustAgent


class ScopedTrustAgent(TrustAgent):
    """A ConnectOnion ``TrustAgent`` whose mutable state belongs to one agent."""

    def __init__(self, trust: str, *, co_dir: Path) -> None:
        super().__init__(trust)
        self.co_dir = Path(co_dir).resolve()
        self.logger = logging.getLogger(f"co_studio.trust.{self.co_dir.parent.name}")

    def _list_path(self, list_name: str) -> Path:
        return self.co_dir / f"{list_name}.txt"

    def _check_list(self, list_name: str, client_id: str) -> bool:
        try:
            entries = self._list_path(list_name).read_text(encoding="utf-8").splitlines()
        except OSError:
            return False
        for raw in entries:
            entry = raw.strip()
            if not entry or entry.startswith("#"):
                continue
            if entry == client_id:
                return True
            # Preserve ConnectOnion 1.2.1's wildcard semantics for compatibility.
            if "*" in entry and entry.replace("*", "") in client_id:
                return True
        return False

    def _add_to_list(self, list_name: str, client_id: str) -> None:
        if self._check_list(list_name, client_id):
            return
        self.co_dir.mkdir(parents=True, exist_ok=True)
        with self._list_path(list_name).open("a", encoding="utf-8") as stream:
            stream.write(f"{client_id}\n")

    def _remove_from_list(self, list_name: str, client_id: str) -> None:
        path = self._list_path(list_name)
        try:
            lines = path.read_text(encoding="utf-8").splitlines()
        except OSError:
            return
        kept = [line for line in lines if line.strip() != client_id]
        if kept != lines:
            path.write_text("\n".join(kept) + ("\n" if kept else ""), encoding="utf-8")

    def should_allow(self, client_id: str, request: dict | None = None) -> Decision:
        """Evaluate the framework policy using only this agent's trust files."""
        request = request or {}
        config = self._config

        if "blocked" in config.get("deny", ["blocked"]) and self.is_blocked(client_id):
            return Decision(allow=False, reason="Denied by scoped blocklist")

        allow = config.get("allow", [])
        if "whitelisted" in allow and self.is_whitelisted(client_id):
            return Decision(allow=True, reason="Allowed by scoped whitelist")
        if "contact" in allow and self.is_contact(client_id):
            return Decision(allow=True, reason="Allowed by scoped contacts")

        onboard = config.get("onboard", {})
        valid_codes = onboard.get("invite_code", [])
        if isinstance(valid_codes, str):
            valid_codes = [valid_codes]
        request_code = request.get("invite_code")
        if request_code and request_code in valid_codes:
            self.promote_to_contact(client_id)
            return Decision(allow=True, reason="Allowed by scoped invite onboarding")

        required_payment = onboard.get("payment")
        request_payment = request.get("payment", 0)
        try:
            payment_sufficient = bool(required_payment) and float(request_payment) >= float(required_payment)
        except (TypeError, ValueError):
            payment_sufficient = False
        if payment_sufficient:
            self.promote_to_contact(client_id)
            return Decision(allow=True, reason="Allowed by scoped payment onboarding")

        default = config.get("default", "deny")
        if default == "allow":
            return Decision(allow=True, reason="Allowed by policy default")
        if default == "deny":
            return Decision(allow=False, reason="Denied by policy default")
        if default == "ask":
            if onboard and (onboard.get("invite_code") or onboard.get("payment")):
                return Decision(allow=False, reason="Onboard required")
            return self._llm_decide(client_id, request)
        return Decision(allow=False, reason="Denied by invalid policy default")

    # Verification in the base class calls these overridden promotion/query methods.
    def promote_to_contact(self, client_id: str) -> str:
        self._add_to_list("contacts", client_id)
        return f"{client_id} promoted to contact."

    def promote_to_whitelist(self, client_id: str) -> str:
        self._add_to_list("whitelist", client_id)
        return f"{client_id} promoted to whitelist."

    def demote_to_contact(self, client_id: str) -> str:
        self._remove_from_list("whitelist", client_id)
        self._add_to_list("contacts", client_id)
        return f"{client_id} demoted to contact."

    def demote_to_stranger(self, client_id: str) -> str:
        self._remove_from_list("contacts", client_id)
        self._remove_from_list("whitelist", client_id)
        return f"{client_id} demoted to stranger."

    def block(self, client_id: str, reason: str = "") -> str:
        self._add_to_list("blocklist", client_id)
        return f"{client_id} blocked. Reason: {reason}"

    def unblock(self, client_id: str) -> str:
        self._remove_from_list("blocklist", client_id)
        return f"{client_id} unblocked."

    def get_level(self, client_id: str) -> str:
        if self.is_blocked(client_id):
            return "blocked"
        if self.is_whitelisted(client_id):
            return "whitelist"
        if self.is_contact(client_id):
            return "contact"
        return "stranger"

    def is_whitelisted(self, client_id: str) -> bool:
        return self._check_list("whitelist", client_id)

    def is_blocked(self, client_id: str) -> bool:
        return self._check_list("blocklist", client_id)

    def is_contact(self, client_id: str) -> bool:
        return self._check_list("contacts", client_id)

    def is_stranger(self, client_id: str) -> bool:
        return self.get_level(client_id) == "stranger"

    def get_self_address(self) -> str | None:
        try:
            from connectonion import address

            data = address.load(self.co_dir)
        except Exception:  # noqa: BLE001 - absent/corrupt identity means no super-admin
            return None
        return str(data["address"]) if data and data.get("address") else None

    def _admin_ids(self) -> set[str]:
        admins = {address} if (address := self.get_self_address()) else set()
        try:
            lines = self._list_path("admins").read_text(encoding="utf-8").splitlines()
        except OSError:
            return admins
        admins.update(line.strip() for line in lines if line.strip() and not line.lstrip().startswith("#"))
        return admins

    def is_admin(self, client_id: str) -> bool:
        return client_id in self._admin_ids()

    def is_super_admin(self, client_id: str) -> bool:
        return client_id == self.get_self_address()

    def add_admin(self, admin_id: str) -> str:
        if admin_id in self._admin_ids():
            return f"{admin_id} is already an admin."
        self._add_to_list("admins", admin_id)
        return f"{admin_id} added as admin."

    def remove_admin(self, admin_id: str) -> str:
        if not self._check_list("admins", admin_id):
            return f"{admin_id} is not an admin."
        self._remove_from_list("admins", admin_id)
        return f"{admin_id} removed from admins."


def scope_host(host_fn: Callable[..., Any]) -> Callable[..., Any]:
    """Wrap ConnectOnion's ``host`` so string policies use agent-scoped state."""
    if getattr(host_fn, "_co_studio_scoped_trust", False):
        return host_fn

    @functools.wraps(host_fn)
    def wrapped(agent: Any, *args: Any, **kwargs: Any) -> Any:
        co_dir = kwargs.get("co_dir")
        trust = kwargs.get("trust", "careful")
        if co_dir is not None and isinstance(trust, str):
            kwargs["trust"] = ScopedTrustAgent(trust, co_dir=Path(co_dir))
            print(f"[co-studio] trust state scoped to {Path(co_dir).resolve()}", flush=True)
        return host_fn(agent, *args, **kwargs)

    wrapped._co_studio_scoped_trust = True  # type: ignore[attr-defined]
    return wrapped
