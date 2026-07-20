"""Assemble the Copy-for-Claude markdown diagnostics bundle."""

from __future__ import annotations

from . import logs, registry, setup_check
from .registry import AgentMeta
from .supervisor import SUPERVISOR, fetch_info

_RELAY_LABEL = {True: "✓ connected", False: "✗ trouble", None: "unknown"}


def _installed_version() -> str:
    """Framework version from the studio's own environment (fallback when agent is down)."""
    try:
        import connectonion

        return str(getattr(connectonion, "__version__", "unknown"))
    except Exception:  # noqa: BLE001
        return "unknown"


def build(meta: AgentMeta) -> str:
    """One paste-ready markdown bundle with everything Claude needs to debug this agent."""
    agent_dir = registry.agent_dir(meta.slug)
    stdout_log = SUPERVISOR.current_log_path(meta.slug)   # this run's log (or latest on disk)
    state = SUPERVISOR.state_of(meta.slug)
    endpoints, relay = logs.parse_runtime_signals(stdout_log)
    info = fetch_info(meta.port) if state == "online" else None
    version = (info or {}).get("version") or _installed_version()

    endpoints_note = f" (announced {endpoints} endpoints)" if endpoints is not None else ""
    stdout_tail = logs.read_tail(stdout_log, 20)
    logger_tail = logs.read_tail(logs.logger_log_path(agent_dir), 200)
    traceback = logs.find_last_traceback(logs.read_tail(stdout_log, 400)) or logs.find_last_traceback(logger_tail)
    events = logs.parse_events(logger_tail or stdout_tail)
    doctor = setup_check.run_doctor()

    lines = [
        f"## Agent: {meta.name}",
        f"- address: {meta.address}   port: {meta.port}   state: {state}",
        f"- relay: {_RELAY_LABEL[relay]}{endpoints_note}",
        f"- model: {meta.model}   template: {meta.preset}   toolkits: {', '.join(meta.toolkits)}   framework: connectonion {version}",
        f"- script: {agent_dir / 'agent.py'}",
        f"- co_dir: {agent_dir / '.co'}",
        "",
        "### Last error",
        "```text",
        traceback or SUPERVISOR.last_error_of(meta.slug) or "(none found)",
        "```",
        "",
        "### Recent events",
        events or "(no events parsed)",
        "",
        "### Last 20 log lines (stdout)",
        "```text",
        *(stdout_tail or ["(empty)"]),
        "```",
        "",
        "### Environment doctor",
        *(f"- {'✓' if entry['ok'] else '✗'} {entry['check']} — {entry['detail']}" for entry in doctor),
    ]
    return "\n".join(lines) + "\n"
